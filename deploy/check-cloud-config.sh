#!/usr/bin/env bash
set -Eeuo pipefail
set +x

config=/opt/datashield/secrets/cloud.env
if [[ ! -f "$config" || -L "$config" ]]; then
  echo 'Missing required configuration: CLOUD_ENV_FILE' >&2
  exit 1
fi
if [[ "$(stat -c '%U:%G:%a' "$config")" != root:root:600 ]]; then
  echo 'Unsafe configuration permissions: CLOUD_ENV_FILE' >&2
  exit 1
fi

# cloud.env is root-owned and mode 0600. Suppress parser diagnostics so a
# malformed line can never put an operator-provided value into deployment logs.
if ! . "$config" >/dev/null 2>&1; then
  echo 'Invalid configuration syntax: CLOUD_ENV_FILE' >&2
  exit 1
fi

missing=()
for name in CLOUD_SECRETS_DIR COMPOSE_PROJECT_NAME CLOUD_BIND_ADDRESS IDENTITY_BIND_ADDRESS CLOUD_HTTP_BIND_ADDRESS CLOUD_HTTPS_BIND_ADDRESS CLOUD_DOMAIN SCHEDULER_ENABLED IDENTITY_EMAIL_VERIFY_REQUIRED IDENTITY_SMTP_HOST IDENTITY_SMTP_PORT IDENTITY_SMTP_USER IDENTITY_EMAIL_FROM IDENTITY_SMTP_STARTTLS IDENTITY_LLM_MODEL; do
  if [[ -z "${!name:-}" ]]; then missing+=("$name"); fi
done
[[ "${IDENTITY_EMAIL_VERIFY_REQUIRED:-}" == true ]] || missing+=(IDENTITY_EMAIL_VERIFY_REQUIRED)
[[ "${IDENTITY_BIND_ADDRESS:-}" == 127.0.0.1 ]] || missing+=(IDENTITY_BIND_ADDRESS)
[[ "${CLOUD_BIND_ADDRESS:-}" == 127.0.0.1 ]] || missing+=(CLOUD_BIND_ADDRESS)
[[ "${CLOUD_HTTP_BIND_ADDRESS:-}" == 0.0.0.0 ]] || missing+=(CLOUD_HTTP_BIND_ADDRESS)
[[ "${CLOUD_HTTPS_BIND_ADDRESS:-}" == 0.0.0.0 ]] || missing+=(CLOUD_HTTPS_BIND_ADDRESS)
[[ "${COMPOSE_PROJECT_NAME:-}" == datashield-cloud ]] || missing+=(COMPOSE_PROJECT_NAME)
[[ "${CLOUD_DOMAIN:-}" =~ ^[A-Za-z0-9.-]+$ ]] || missing+=(CLOUD_DOMAIN)
[[ "${SCHEDULER_ENABLED:-}" == true || "${SCHEDULER_ENABLED:-}" == false ]] || missing+=(SCHEDULER_ENABLED)
[[ "${IDENTITY_SMTP_STARTTLS:-}" == true || "${IDENTITY_SMTP_STARTTLS:-}" == false ]] || missing+=(IDENTITY_SMTP_STARTTLS)
[[ "${IDENTITY_SMTP_PORT:-}" =~ ^[0-9]{1,5}$ ]] && (( IDENTITY_SMTP_PORT > 0 && IDENTITY_SMTP_PORT < 65536 )) || missing+=(IDENTITY_SMTP_PORT)
[[ "${CLOUD_SECRETS_DIR:-}" == /opt/datashield-cloud/secrets ]] || missing+=(CLOUD_SECRETS_DIR)

secrets="${CLOUD_SECRETS_DIR:-/opt/datashield-cloud/secrets}"
if [[ ! -d "$secrets" || -L "$secrets" ]]; then
  missing+=(CLOUD_SECRETS_DIR)
fi

check_secret_path() {
  local variable="$1" file="$2"
  if [[ ! -f "$file" || -L "$file" || ! -s "$file" ]]; then
    missing+=("$variable")
    return
  fi
  local owner mode
  owner="$(stat -c '%U' "$file")"
  mode="$(stat -c '%a' "$file")"
  if [[ ( "$owner" != root && "$owner" != admin ) || "$mode" != 600 ]]; then
    missing+=("$variable")
  fi
}

check_secret_path POSTGRES_PASSWORD_FILE "$secrets/postgres_password"
check_secret_path DATABASE_URL_FILE "$secrets/cloud_database_url"
check_secret_path CLOUD_ADMIN_TOKEN_FILE "$secrets/cloud_admin_token"
check_secret_path IDENTITY_DATABASE_URL_FILE "$secrets/identity_database_url"
check_secret_path IDENTITY_SMTP_PASSWORD_FILE "$secrets/identity_smtp_password"
check_secret_path IDENTITY_LLM_API_KEY_FILE "$secrets/identity_llm_api_key"
check_secret_path GHCR_PULL_TOKEN_FILE /opt/datashield/secrets/ghcr_pull_token

if ((${#missing[@]})); then
  printf 'Cloud production configuration is missing or unsafe: %s\n' "$(printf '%s\n' "${missing[@]}" | sort -u | paste -sd, -)" >&2
  exit 1
fi
echo 'Cloud production configuration preflight passed.'
