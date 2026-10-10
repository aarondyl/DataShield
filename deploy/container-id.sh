#!/usr/bin/env bash

# docker ps -q may print a short ID while docker compose ps -q prints a full
# one. Resolve both forms through Docker before comparing container identity.
container_full_id() {
  local container_ref="$1"
  local full_id

  full_id="$(docker inspect --format '{{.Id}}' "$container_ref")" || return 1
  [[ "$full_id" =~ ^[0-9a-f]{64}$ ]] || return 1
  printf '%s\n' "$full_id"
}
