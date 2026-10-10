#!/usr/bin/env bash
set -Eeuo pipefail
set +x
umask 077

if [[ "$(id -u)" -ne 0 ]]; then
  echo 'Run this one-time host setup as root through the approved Simple Application Server administration channel.' >&2
  exit 1
fi

repo_root="$(cd -- "$(dirname -- "$0")/.." && pwd)"
libexec=/usr/local/libexec/datashield-cloud
wrapper=/usr/local/sbin/datashield-cloud-deploy
sudoers=/etc/sudoers.d/datashield-cloud-deploy
compose_file=/opt/datashield/docker-compose.cloud.yml

install -d -o root -g root -m 0755 "$libexec"
install -o root -g root -m 0755 "$repo_root/deploy/datashield-cloud-deploy" "$wrapper"
install -o root -g root -m 0755 "$repo_root/deploy/prepare-cloud-secrets.sh" "$libexec/prepare-cloud-secrets.sh"
install -o root -g root -m 0755 "$repo_root/deploy/check-cloud-config.sh" "$libexec/check-cloud-config.sh"
install -o root -g root -m 0644 "$repo_root/deploy/cloud.env.example" "$libexec/cloud.env.example"

# Keep a host's existing Compose definition intact. The fixed deploy helper
# uses the installed file only for its initial preflight; SHA-pinned releases
# get their own immutable copy below /opt/datashield/releases.
if [[ ! -e "$compose_file" ]]; then
  install -o root -g root -m 0600 "$repo_root/docker-compose.cloud.yml" "$compose_file"
elif [[ ! -f "$compose_file" || -L "$compose_file" ]]; then
  echo 'Existing Compose definition is not a regular file; it was left untouched.' >&2
  exit 1
fi

if [[ ! -e "$sudoers" ]]; then
  temp="$(mktemp /etc/sudoers.d/.datashield-cloud-deploy.XXXXXXXX)"
  trap 'rm -f "$temp"' EXIT
  printf 'deploy ALL=(root) NOPASSWD: %s *\n' "$wrapper" > "$temp"
  chmod 0440 "$temp"
  if ! visudo -cf "$temp" >/dev/null 2>&1; then
    echo 'Restricted deploy sudoers rule did not validate; no sudoers file was installed.' >&2
    exit 1
  fi
  install -o root -g root -m 0440 "$temp" "$sudoers"
elif ! grep -Fq "$wrapper" "$sudoers"; then
  echo 'Existing sudoers file conflicts with the required restricted deploy wrapper; it was left unchanged.' >&2
  exit 1
elif [[ "$(cat "$sudoers")" != "deploy ALL=(root) NOPASSWD: $wrapper *" ]]; then
  echo 'Existing sudoers policy is broader or different from the expected single wrapper rule; it was left unchanged.' >&2
  exit 1
fi

"$libexec/prepare-cloud-secrets.sh"

if systemctl is-active --quiet datashield.service 2>/dev/null; then
  echo 'datashield.service is active. It was not changed. First production cutover still requires explicit approval.'
else
  echo 'datashield.service is not active; no service or network settings were changed.'
fi

echo 'Installed fixed root-owned Cloud deploy wrapper and its least-privilege sudo rule.'
echo 'The wrapper requires a one-time production-cutover approval marker before its first deployment.'
