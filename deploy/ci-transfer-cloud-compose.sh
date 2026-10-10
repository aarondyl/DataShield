#!/usr/bin/env bash
set -Eeuo pipefail
set +x
umask 077

die() { printf 'Cloud Compose transfer failed: %s\n' "$1" >&2; exit 1; }
[[ $# -eq 6 ]] || die 'expected source SHA, Compose SHA256, three image digests, and checked-out Compose path'
source_sha="$1"
compose_sha="$2"
cloud_digest="$3"
identity_digest="$4"
proxy_digest="$5"
compose_file="$6"
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]] || die 'invalid validated source SHA'
[[ "$compose_sha" =~ ^[0-9a-f]{64}$ ]] || die 'invalid Compose SHA256'
for digest in "$cloud_digest" "$identity_digest" "$proxy_digest"; do
  [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || die 'invalid immutable image digest'
done
[[ -f "$compose_file" && ! -L "$compose_file" ]] || die 'checked-out Compose file is missing or unsafe'
[[ "$(sha256sum -- "$compose_file" | awk '{print $1}')" == "$compose_sha" ]] || die 'checked-out Compose file differs from the recorded source hash'
[[ "${ECS_USER:-}" == admin && "${ECS_PORT:-}" == 22 && -n "${ECS_HOST:-}" && -n "${ECS_KNOWN_HOSTS:-}" && -n "${ECS_SSH_KEY:-}" ]] \
  || die 'Production SSH configuration is incomplete or does not match the approved admin endpoint'

ssh_dir="$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/datashield-ssh.XXXXXXXX")"
chmod 0700 "$ssh_dir"
key="$ssh_dir/key"
known_hosts="$ssh_dir/known_hosts"
trap 'rm -rf -- "$ssh_dir"' EXIT
printf '%s\n' "$ECS_SSH_KEY" > "$key"
printf '%s\n' "$ECS_KNOWN_HOSTS" > "$known_hosts"
chmod 0600 "$key" "$known_hosts"
target="$ECS_USER@$ECS_HOST"
ssh_options=(-F /dev/null -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$known_hosts" -o ConnectTimeout=10 -i "$key" -p "$ECS_PORT")
remote_upload='set -eu; umask 077; test "$HOME" = /home/admin; base="$HOME/.datashield-cloud-upload"; test ! -L "$base"; mkdir -p "$base"; test "$(stat -c %U "$base")" = admin; chmod 700 "$base"; dir="$base/'"$source_sha"'"; test ! -L "$dir"; mkdir -p "$dir"; test "$(stat -c %U "$dir")" = admin; chmod 700 "$dir"; tmp="$dir/.compose.upload.$$"; trap '\''rm -f -- "$tmp"'\'' EXIT; cat > "$tmp"; chmod 600 "$tmp"; mv -f -- "$tmp" "$dir/docker-compose.cloud.yml"'

# The content is sent on SSH stdin. The remote shell publishes it atomically
# only after the complete stream arrives; the root wrapper validates its hash.
ssh "${ssh_options[@]}" "$target" "$remote_upload" < "$compose_file" || die 'SSH Compose transfer failed'
ssh "${ssh_options[@]}" "$target" \
  "sudo -n /usr/local/sbin/datashield-cloud-deploy stage $source_sha $compose_sha $cloud_digest $identity_digest $proxy_digest" \
  || die 'server rejected the uploaded Compose artifact'
ssh "${ssh_options[@]}" "$target" \
  "sudo -n /usr/local/sbin/datashield-cloud-deploy diagnose $source_sha $compose_sha $cloud_digest $identity_digest $proxy_digest" \
  || die 'read-only deployment diagnosis failed; production activation was not requested'
ssh "${ssh_options[@]}" "$target" \
  "sudo -n /usr/local/sbin/datashield-cloud-deploy deploy $source_sha $compose_sha $cloud_digest $identity_digest $proxy_digest" \
  || die 'production deployment wrapper returned an error'
