#!/usr/bin/env bash
set -Eeuo pipefail
set +x
umask 077

if [[ "$(id -u)" -ne 0 ]]; then
  echo 'Run this one-time host setup as root through the approved Simple Application Server administration channel.' >&2
  exit 1
fi

repo_root="$(cd -- "$(dirname -- "$0")/.." && pwd)"
source "$repo_root/deploy/container-id.sh"
libexec=/usr/local/libexec/datashield-cloud
wrapper=/usr/local/sbin/datashield-cloud-deploy
sudoers=/etc/sudoers.d/datashield-cloud-deploy
project_dir=/opt/datashield-cloud/source
root=/opt/datashield
config_dir="$root/secrets"
legacy_secrets=/opt/datashield-cloud/secrets

# Finish every host-state preflight before creating files or changing policy.
id deploy >/dev/null 2>&1 || { echo 'Dedicated deploy account is missing; no host changes were made.' >&2; exit 1; }
command -v visudo >/dev/null 2>&1 || { echo 'visudo is unavailable; no host changes were made.' >&2; exit 1; }
if [[ -e "$sudoers" ]]; then
  [[ -f "$sudoers" && ! -L "$sudoers" ]] || { echo 'Existing deployment sudoers path is not a regular file; no host changes were made.' >&2; exit 1; }
  [[ "$(stat -c '%U:%G:%a' "$sudoers")" == root:root:440 ]] || { echo 'Existing deployment sudoers file has unsafe ownership or mode; no host changes were made.' >&2; exit 1; }
  [[ "$(cat "$sudoers")" == "deploy ALL=(root) NOPASSWD: $wrapper *" ]] || { echo 'Existing sudoers policy differs from the restricted wrapper rule; no host changes were made.' >&2; exit 1; }
fi

[[ -x "$repo_root/deploy/datashield-cloud-deploy" && -f "$repo_root/deploy/container-id.sh" && -x "$repo_root/deploy/prepare-cloud-secrets.sh" && -x "$repo_root/deploy/check-cloud-config.sh" && -f "$repo_root/deploy/cloud.env.example" ]] \
  || { echo 'Deployment helper files are incomplete; no host changes were made.' >&2; exit 1; }
[[ -d "$legacy_secrets" && ! -L "$legacy_secrets" && "$(stat -c '%a' "$legacy_secrets")" == 700 ]] \
  || { echo 'Existing legacy Cloud Secret directory is missing or not mode 0700; no host changes were made.' >&2; exit 1; }
if [[ -e "$root" ]]; then
  [[ -d "$root" && ! -L "$root" ]] || { echo 'Deployment root is not a real directory; no host changes were made.' >&2; exit 1; }
fi
if [[ -e "$config_dir" ]]; then
  [[ -d "$config_dir" && ! -L "$config_dir" ]] || { echo 'Deployment Secret path is not a real directory; no host changes were made.' >&2; exit 1; }
fi
if [[ -e "$config_dir/cloud.env" ]]; then
  [[ -f "$config_dir/cloud.env" && ! -L "$config_dir/cloud.env" && "$(stat -c '%U:%G:%a' "$config_dir/cloud.env")" == root:root:600 ]] \
    || { echo 'Existing cloud.env is not a root-owned mode 0600 regular file; no host changes were made.' >&2; exit 1; }
  grep -Fxq "CLOUD_SECRETS_DIR=$legacy_secrets" "$config_dir/cloud.env" \
    || { echo 'Existing cloud.env does not preserve the legacy Cloud Secret directory; no host changes were made.' >&2; exit 1; }
fi
for secret_name in postgres_password cloud_database_url cloud_admin_token identity_database_url identity_smtp_password identity_llm_api_key; do
  secret_file="$legacy_secrets/$secret_name"
  if [[ -e "$secret_file" ]]; then
    [[ -f "$secret_file" && ! -L "$secret_file" && "$(stat -c '%a' "$secret_file")" == 600 ]] \
      || { printf 'Existing Secret %s has unsafe type or mode; no host changes were made.\n' "$secret_name" >&2; exit 1; }
    secret_owner="$(stat -c '%U' "$secret_file")"
    [[ "$secret_owner" == root || "$secret_owner" == admin ]] \
      || { printf 'Existing Secret %s has unexpected ownership; no host changes were made.\n' "$secret_name" >&2; exit 1; }
  fi
done
if [[ -e "$config_dir/ghcr_pull_token" ]]; then
  [[ -f "$config_dir/ghcr_pull_token" && ! -L "$config_dir/ghcr_pull_token" && "$(stat -c '%U:%G:%a' "$config_dir/ghcr_pull_token")" == root:root:600 ]] \
    || { echo 'Existing GHCR token file has unsafe type, ownership or mode; no host changes were made.' >&2; exit 1; }
fi

if [[ ! -f "$project_dir/docker-compose.cloud.yml" || ! -f "$project_dir/docker-compose.ecs.yml" ]]; then
  echo 'Existing source Compose files are not both present; no host changes were made.' >&2
  exit 1
fi
command -v docker >/dev/null && docker info >/dev/null 2>&1 || { echo 'Docker daemon unavailable; no host changes were made.' >&2; exit 1; }
pg_ids="$(docker ps -q --filter label=com.docker.compose.project=source --filter label=com.docker.compose.service=postgres)"
[[ "$(printf '%s\n' "$pg_ids" | sed '/^$/d' | wc -l)" -eq 1 ]] || { echo 'Expected one running PostgreSQL container in project source; no host changes were made.' >&2; exit 1; }
pg_ref="$(printf '%s\n' "$pg_ids" | sed '/^$/d')"
pg_id="$(container_full_id "$pg_ref")" || { echo 'Could not resolve running PostgreSQL container ID; no host changes were made.' >&2; exit 1; }
[[ "$(docker inspect --format '{{.State.Health.Status}}' "$pg_id")" == healthy ]] || { echo 'Existing PostgreSQL container is not healthy; no host changes were made.' >&2; exit 1; }
pg_volume="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' "$pg_id")"
[[ "$pg_volume" == source_cloud_postgres_data ]] || { echo 'PostgreSQL is not mounted on source_cloud_postgres_data; no host changes were made.' >&2; exit 1; }
docker volume inspect source_cloud_postgres_data >/dev/null 2>&1 || { echo 'Expected PostgreSQL volume missing; no host changes were made.' >&2; exit 1; }
pg_networks="$(docker inspect --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}' "$pg_id")"
[[ " $pg_networks " == *" source_cloud_database "* ]] || { echo 'PostgreSQL is not attached to source_cloud_database; no host changes were made.' >&2; exit 1; }
compose_pg_ref="$(docker compose --project-name source --project-directory "$project_dir" -f "$project_dir/docker-compose.cloud.yml" -f "$project_dir/docker-compose.ecs.yml" ps -q postgres 2>/dev/null)"
compose_pg="$(container_full_id "$compose_pg_ref")" || { echo 'Could not resolve Compose PostgreSQL container ID; no host changes were made.' >&2; exit 1; }
[[ "$compose_pg" == "$pg_id" ]] || { echo 'Compose files do not resolve to the running source PostgreSQL; no host changes were made.' >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo 'python3 is unavailable for safe Compose identity validation; no host changes were made.' >&2; exit 1; }
docker compose --project-name source --project-directory "$project_dir" -f "$project_dir/docker-compose.cloud.yml" -f "$project_dir/docker-compose.ecs.yml" config --format json 2>/dev/null \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); v=d["volumes"]["cloud_postgres_data"]; assert v.get("name")=="source_cloud_postgres_data"; assert d["networks"]["cloud_database"].get("name")=="source_cloud_database"; assert any(x.get("host_ip")=="127.0.0.1" and x.get("published")=="8000" for x in d["services"]["cloud"]["ports"])' \
  || { echo 'Current Compose definition does not resolve the approved PostgreSQL volume, database network and Cloud loopback port; no host changes were made.' >&2; exit 1; }
cloud_ids="$(docker ps -q --filter label=com.docker.compose.project=source --filter label=com.docker.compose.service=cloud)"
[[ "$(printf '%s\n' "$cloud_ids" | sed '/^$/d' | wc -l)" -eq 1 ]] || { echo 'Expected one existing Cloud container; no host changes were made.' >&2; exit 1; }
[[ "$(docker inspect --format '{{.State.Health.Status}}' "$cloud_ids")" == healthy ]] || { echo 'Existing Cloud container is not healthy; no host changes were made.' >&2; exit 1; }
cloud_port="$(docker inspect --format '{{range $port, $bindings := .NetworkSettings.Ports}}{{if eq $port "8000/tcp"}}{{range $bindings}}{{.HostIp}}:{{.HostPort}}{{end}}{{end}}{{end}}' "$cloud_ids")"
[[ "$cloud_port" == 127.0.0.1:8000 ]] || { echo 'Existing Cloud port mapping differs from 127.0.0.1:8000; no host changes were made.' >&2; exit 1; }
for port in 80 443 8001; do
  listener_count="$(ss -lnt "( sport = :$port )" 2>/dev/null | tail -n +2 | wc -l)"
  published_count="$(docker ps -q --filter "publish=$port" | wc -l)"
  if [[ "$listener_count" -gt 0 || "$published_count" -gt 0 ]]; then
    printf 'TCP port %s is already in use; no host changes were made.\n' "$port" >&2
    exit 1
  fi
done

install -d -o root -g root -m 0755 "$libexec"
install -o root -g root -m 0644 "$repo_root/deploy/container-id.sh" "$libexec/container-id.sh"
install -o root -g root -m 0755 "$repo_root/deploy/datashield-cloud-deploy" "$wrapper"
install -o root -g root -m 0755 "$repo_root/deploy/prepare-cloud-secrets.sh" "$libexec/prepare-cloud-secrets.sh"
install -o root -g root -m 0755 "$repo_root/deploy/check-cloud-config.sh" "$libexec/check-cloud-config.sh"
install -o root -g root -m 0644 "$repo_root/deploy/cloud.env.example" "$libexec/cloud.env.example"

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
fi

"$libexec/prepare-cloud-secrets.sh"

if systemctl is-active --quiet datashield.service 2>/dev/null; then
  echo 'datashield.service is active. It was not changed. First production cutover still requires explicit approval.'
else
  echo 'datashield.service is not active; no service or network settings were changed.'
fi

echo 'Installed fixed root-owned Cloud deploy wrapper and its least-privilege sudo rule.'
echo 'The wrapper requires a one-time production-cutover approval marker before its first deployment.'
