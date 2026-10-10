#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if [[ "$(id -u)" -ne 0 ]]; then
  echo 'Run this setup step as root through the approved server administration channel.' >&2
  exit 1
fi

root=/opt/datashield
config_dir="$root/secrets"
legacy_secrets=/opt/datashield-cloud/secrets
example="${DATASHIELD_CLOUD_ENV_EXAMPLE:-$(dirname -- "$0")/cloud.env.example}"

install -d -o root -g root -m 0700 "$root" "$root/releases" "$root/backups" "$config_dir"

if [[ ! -e "$config_dir/cloud.env" ]]; then
  if [[ ! -r "$example" ]]; then
    echo 'Required template CLOUD_ENV_TEMPLATE is unavailable.' >&2
    exit 1
  fi
  install -o root -g root -m 0600 "$example" "$config_dir/cloud.env"
  echo 'Created /opt/datashield/secrets/cloud.env from the non-secret template.'
elif [[ ! -f "$config_dir/cloud.env" || -L "$config_dir/cloud.env" ]]; then
  echo 'CLOUD_ENV_FILE must be a regular non-symlink file; existing file left untouched.' >&2
  exit 1
elif [[ "$(stat -c '%U:%G:%a' "$config_dir/cloud.env")" != root:root:600 ]]; then
  echo 'CLOUD_ENV_FILE has unsafe ownership or mode; existing content was not changed.' >&2
  exit 1
fi

if [[ ! -d "$legacy_secrets" || -L "$legacy_secrets" ]]; then
  echo 'Existing CLOUD_SECRETS_DIR is unavailable; refusing to create a new database Secret directory.' >&2
  exit 1
fi
if [[ "$(stat -c '%a' "$legacy_secrets")" != 700 ]]; then
  echo 'Existing CLOUD_SECRETS_DIR must retain its strict 0700 permissions.' >&2
  exit 1
fi
if ! grep -Fxq "CLOUD_SECRETS_DIR=$legacy_secrets" "$config_dir/cloud.env"; then
  echo 'CLOUD_SECRETS_DIR must continue to reference the preserved legacy Secret directory.' >&2
  exit 1
fi

# Create only absent placeholders in the existing private directory. Existing
# values, ownership and metadata are never replaced or changed.
for name in postgres_password cloud_database_url cloud_admin_token identity_database_url identity_smtp_password identity_llm_api_key; do
  file="$legacy_secrets/$name"
  if [[ ! -e "$file" ]]; then
    ( set -o noclobber; : > "$file" )
    chmod 0600 "$file"
    chown root:root "$file"
    printf 'Created empty secret placeholder: %s\n' "$name"
  elif [[ ! -f "$file" || -L "$file" ]]; then
    printf 'Secret file %s must be a regular non-symlink file; existing file left untouched.\n' "$name" >&2
    exit 1
  else
    owner="$(stat -c '%U' "$file")"
    mode="$(stat -c '%a' "$file")"
    if [[ ( "$owner" != root && "$owner" != admin ) || "$mode" != 600 ]]; then
      printf 'Secret file %s has unsafe ownership or mode; existing content was not changed.\n' "$name" >&2
      exit 1
    fi
  fi
done

token="$config_dir/ghcr_pull_token"
if [[ ! -e "$token" ]]; then
  ( set -o noclobber; : > "$token" )
  chmod 0600 "$token"
  chown root:root "$token"
  echo 'Created empty secret placeholder: ghcr_pull_token'
elif [[ ! -f "$token" || -L "$token" || "$(stat -c '%U:%G:%a' "$token")" != root:root:600 ]]; then
  echo 'Secret file ghcr_pull_token has unsafe type, ownership or mode; existing content was not changed.' >&2
  exit 1
fi

echo 'Cloud configuration template is ready; existing legacy Secret contents were preserved.'
