#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd -- "$(dirname -- "$0")/../.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT

full_id=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
short_id="${full_id:0:12}"
cat > "$tmp/docker" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ "$1" == inspect && "$2" == --format && "$3" == '{{.Id}}' ]]
case "$4" in
  0123456789ab|0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef)
    printf '%s\n' 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
    ;;
  *) exit 1 ;;
esac
MOCK
chmod 0755 "$tmp/docker"

PATH="$tmp:$PATH" bash -Eeuo pipefail -c '
  source "$1"
  short="$(container_full_id "$2")"
  full="$(container_full_id "$3")"
  [[ "$short" == "$full" ]]
  [[ "$short" == "$4" ]]
' _ "$repo_root/deploy/container-id.sh" "$short_id" "$full_id" "$full_id"

echo 'Container ID normalization regression test passed.'
