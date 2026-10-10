#!/usr/bin/env bash

# Snapshot and restore only the application services that a release changes.
# PostgreSQL and all volumes are deliberately excluded from these service lists.
save_first_cutover_state() {
  local snapshot_dir="$ROOT/first-cutover-rollback"
  local temp_dir service ids id image running image_ref

  if [[ -e "$snapshot_dir" ]]; then
    [[ -d "$snapshot_dir" && -s "$snapshot_dir/services" && -s "$snapshot_dir/compose.override.yml" ]] \
      || die 'first-cutover rollback snapshot is incomplete; refusing to overwrite it'
    return 0
  fi

  temp_dir="$(mktemp -d "$ROOT/.first-cutover-rollback.XXXXXXXX")"
  chmod 0700 "$temp_dir"
  printf 'postgres|%s\n' "$(existing_postgres_id)" > "$temp_dir/services"
  printf 'services:\n' > "$temp_dir/compose.override.yml"

  for service in cloud identity gateway; do
    ids="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" --filter "label=com.docker.compose.service=$service")"
    [[ "$(printf '%s\n' "$ids" | sed '/^$/d' | wc -l)" -le 1 ]] \
      || { rm -rf -- "$temp_dir"; die "expected at most one prior $service container"; }
    id="$(printf '%s\n' "$ids" | sed '/^$/d')"
    if [[ -z "$id" ]]; then
      printf '%s|absent|false|\n' "$service" >> "$temp_dir/services"
      continue
    fi

    image="$(docker inspect --format '{{.Image}}' "$id")"
    [[ "$image" =~ ^sha256:[0-9a-f]{64}$ ]] \
      || { rm -rf -- "$temp_dir"; die "could not record the prior $service image"; }
    running="$(docker inspect --format '{{.State.Running}}' "$id")"
    [[ "$running" == true || "$running" == false ]] \
      || { rm -rf -- "$temp_dir"; die "could not record the prior $service state"; }
    image_ref="datashield-${service}-rollback:${image#sha256:}"
    docker image tag "$image" "$image_ref"
    printf '%s|present|%s|%s\n' "$service" "$running" "$image_ref" >> "$temp_dir/services"
    printf '  %s:\n    image: %s\n    pull_policy: never\n' "$service" "$image_ref" >> "$temp_dir/compose.override.yml"
  done

  chmod 0600 "$temp_dir/services" "$temp_dir/compose.override.yml"
  mv -- "$temp_dir" "$snapshot_dir"
}

restore_first_cutover_state() {
  local snapshot_dir="$ROOT/first-cutover-rollback"
  local line service state was_running image_ref expected_postgres ids id image health running
  local -a present_services=() absent_services=() stopped_services=()

  [[ -s "$snapshot_dir/services" && -s "$snapshot_dir/compose.override.yml" ]] \
    || { log 'first-cutover rollback snapshot is unavailable'; return 1; }
  expected_postgres="$(sed -n 's/^postgres|//p' "$snapshot_dir/services")"
  [[ "$expected_postgres" =~ ^[0-9a-f]{64}$ ]] \
    || { log 'first-cutover rollback PostgreSQL identity is invalid'; return 1; }

  while IFS='|' read -r service state was_running image_ref; do
    case "$service" in
      postgres) continue ;;
      cloud|identity|gateway) ;;
      *) log 'first-cutover rollback snapshot contains an unknown service'; return 1 ;;
    esac
    if [[ "$state" == absent ]]; then
      absent_services+=("$service")
    elif [[ "$state" == present && ( "$was_running" == true || "$was_running" == false ) && "$image_ref" =~ ^datashield-(cloud|identity|gateway)-rollback:[0-9a-f]{64}$ ]]; then
      present_services+=("$service")
      [[ "$was_running" == true ]] || stopped_services+=("$service")
    else
      log 'first-cutover rollback snapshot is malformed'
      return 1
    fi
  done < "$snapshot_dir/services"

  [[ " ${present_services[*]} " == *" cloud "* ]] \
    || { log 'first-cutover rollback snapshot does not include the prior Cloud service'; return 1; }

  BASE="$PROJECT_DIR/docker-compose.cloud.yml"
  EXTRA_FILES+=(--file "$snapshot_dir/compose.override.yml")
  if ! compose --profile production --profile identity up -d --no-build --no-deps "${present_services[@]}" >> "$LOG" 2>&1; then
    log 'first-cutover application image restoration failed'
    return 1
  fi

  if ((${#stopped_services[@]})); then
    if ! compose --profile production --profile identity stop "${stopped_services[@]}" >> "$LOG" 2>&1; then
      log 'first-cutover prior stopped-service restoration failed'
      return 1
    fi
  fi

  if ((${#absent_services[@]})); then
    # The pre-cutover Compose file may not define a newly introduced service.
    # Remove only its project/service-labeled containers; never touch volumes.
    local service ids
    for service in "${absent_services[@]}"; do
      ids="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" --filter "label=com.docker.compose.service=$service")"
      if [[ -n "$ids" ]] && ! docker rm --force $ids >> "$LOG" 2>&1; then
        log "first-cutover removal of newly introduced $service application container failed"
        return 1
      fi
    done
  fi

  while IFS='|' read -r service state was_running image_ref; do
    [[ "$state" == present ]] || continue
    ids="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" --filter "label=com.docker.compose.service=$service")"
    [[ "$(printf '%s\n' "$ids" | sed '/^$/d' | wc -l)" -eq 1 ]] \
      || { log "restored $service container count differs from the pre-cutover state"; return 1; }
    id="$(printf '%s\n' "$ids" | sed '/^$/d')"
    image="$(docker inspect --format '{{.Image}}' "$id")"
    running="$(docker inspect --format '{{.State.Running}}' "$id")"
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$id")"
    [[ "${image#sha256:}" == "${image_ref##*:}" ]] \
      || { log "restored $service image differs from its saved image"; return 1; }
    if [[ "$was_running" == true ]]; then
      [[ "$running" == true && ( "$health" == healthy || "$health" == none ) ]] \
        || { log "restored $service is not running healthy"; return 1; }
    else
      [[ "$running" == false ]] || { log "restored $service should remain stopped"; return 1; }
    fi
  done < "$snapshot_dir/services"

  local actual_postgres
  actual_postgres="$(existing_postgres_id)" || return 1
  if [[ "$actual_postgres" != "$expected_postgres" ]]; then
    log 'PostgreSQL container identity changed during application rollback; investigate immediately'
    return 1
  fi
  local data_mount
  data_mount="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' "$actual_postgres")"
  if [[ "$data_mount" != source_cloud_postgres_data ]]; then
    log 'PostgreSQL data volume identity changed during application rollback; investigate immediately'
    return 1
  fi

  log 'first-cutover Cloud, Identity and Proxy application state restored; PostgreSQL and its data volume were untouched'
}

rollback_after_failed_activation() {
  local status="$1"
  if [[ "$status" -ne 0 && "${activation_started:-0}" -eq 1 ]]; then
    restore_previous_cloud || true
  fi
}
