#!/usr/bin/env bash

# Stage and validate the reviewed Compose input transferred by the CI runner.
# No network fetch is performed on the production host.
ARTIFACT_ROOT_OWNER=root
ARTIFACT_UPLOAD_OWNER=admin

validate_release_arguments() {
  local source_sha="$1" compose_sha="$2" cloud_digest="$3" identity_digest="$4" proxy_digest="$5"
  [[ "$source_sha" =~ ^[0-9a-f]{40}$ ]] || die 'invalid source commit SHA'
  [[ "$compose_sha" =~ ^[0-9a-f]{64}$ ]] || die 'invalid Compose SHA256'
  [[ "$cloud_digest" =~ ^sha256:[0-9a-f]{64}$ && "$identity_digest" =~ ^sha256:[0-9a-f]{64}$ && "$proxy_digest" =~ ^sha256:[0-9a-f]{64}$ ]] \
    || die 'release images must use immutable SHA256 digests'
}

release_dir_for_sha() {
  printf '%s/releases/%s\n' "$ROOT" "$1"
}

expected_release_manifest() {
  printf 'DATASHIELD_RELEASE_SHA=%s\nCOMPOSE_SHA256=%s\nCLOUD_DIGEST=%s\nIDENTITY_DIGEST=%s\nPROXY_DIGEST=%s\n' \
    "$1" "$2" "$3" "$4" "$5"
}

assert_staged_compose_release() {
  local source_sha="$1" compose_sha="$2" cloud_digest="$3" identity_digest="$4" proxy_digest="$5"
  local release_dir compose_file manifest actual_sha

  validate_release_arguments "$source_sha" "$compose_sha" "$cloud_digest" "$identity_digest" "$proxy_digest"
  release_dir="$(release_dir_for_sha "$source_sha")"
  compose_file="$release_dir/docker-compose.cloud.yml"
  manifest="$release_dir/release.manifest"
  [[ -d "$release_dir" && ! -L "$release_dir" && "$(stat -c '%U:%a' "$release_dir")" == "$ARTIFACT_ROOT_OWNER:700" ]] \
    || die 'verified release directory is missing or has unsafe ownership or mode'
  [[ -f "$compose_file" && ! -L "$compose_file" && "$(stat -c '%U:%a' "$compose_file")" == "$ARTIFACT_ROOT_OWNER:600" ]] \
    || die 'verified Compose file is missing or has unsafe ownership or mode'
  [[ -f "$manifest" && ! -L "$manifest" && "$(stat -c '%U:%a' "$manifest")" == "$ARTIFACT_ROOT_OWNER:600" ]] \
    || die 'verified release manifest is missing or has unsafe ownership or mode'
  expected_release_manifest "$source_sha" "$compose_sha" "$cloud_digest" "$identity_digest" "$proxy_digest" \
    | cmp -s - "$manifest" || die 'release manifest does not match the requested source, Compose hash, and image digests'
  actual_sha="$(sha256sum -- "$compose_file" | awk '{print $1}')"
  [[ "$actual_sha" == "$compose_sha" ]] || die 'staged Compose file SHA256 does not match the verified artifact'
  printf '%s\n' "$compose_file"
}

stage_compose_release() {
  local source_sha="$1" compose_sha="$2" cloud_digest="$3" identity_digest="$4" proxy_digest="$5"
  local admin_home upload_root upload_dir upload_file release_dir temp_dir manifest_tmp actual_sha

  validate_release_arguments "$source_sha" "$compose_sha" "$cloud_digest" "$identity_digest" "$proxy_digest"
  admin_home="$(getent passwd admin | awk -F: 'NR == 1 {print $6}')"
  [[ "$admin_home" == /* && "$admin_home" != *'/../'* && "$admin_home" != */.. && -d "$admin_home" && ! -L "$admin_home" && "$(stat -c '%U' "$admin_home")" == "$ARTIFACT_UPLOAD_OWNER" ]] \
    || die 'dedicated admin home could not be validated for Compose upload'
  upload_root="$admin_home/.datashield-cloud-upload"
  upload_dir="$upload_root/$source_sha"
  upload_file="$upload_dir/docker-compose.cloud.yml"
  [[ -d "$upload_root" && ! -L "$upload_root" && "$(stat -c '%U:%a' "$upload_root")" == "$ARTIFACT_UPLOAD_OWNER:700" ]] \
    || die 'temporary Compose upload directory is missing or unsafe'
  [[ -d "$upload_dir" && ! -L "$upload_dir" && "$(stat -c '%U:%a' "$upload_dir")" == "$ARTIFACT_UPLOAD_OWNER:700" ]] \
    || die 'temporary Compose upload version directory is missing or unsafe'
  [[ -f "$upload_file" && ! -L "$upload_file" && "$(stat -c '%U:%a' "$upload_file")" == "$ARTIFACT_UPLOAD_OWNER:600" ]] \
    || die 'uploaded Compose file is missing or has unsafe ownership or mode'
  actual_sha="$(sha256sum -- "$upload_file" | awk '{print $1}')"
  [[ "$actual_sha" == "$compose_sha" ]] || die 'uploaded Compose file SHA256 does not match the CI-verified artifact'

  release_dir="$(release_dir_for_sha "$source_sha")"
  if [[ -e "$release_dir" ]]; then
    [[ -d "$release_dir" && ! -L "$release_dir" && "$(stat -c '%U:%a' "$release_dir")" == "$ARTIFACT_ROOT_OWNER:700" ]] \
      || die 'existing release directory is unsafe; refusing to replace it'
    [[ -f "$release_dir/docker-compose.cloud.yml" && ! -L "$release_dir/docker-compose.cloud.yml" \
      && "$(stat -c '%U:%a' "$release_dir/docker-compose.cloud.yml")" == "$ARTIFACT_ROOT_OWNER:600" ]] \
      || die 'existing release Compose file is unsafe; refusing to replace it'
    actual_sha="$(sha256sum -- "$release_dir/docker-compose.cloud.yml" | awk '{print $1}')"
    [[ "$actual_sha" == "$compose_sha" ]] || die 'existing release Compose file differs from this validated commit'
    if [[ ! -e "$release_dir/release.manifest" ]]; then
      manifest_tmp="$(mktemp "$release_dir/.release.manifest.XXXXXXXX")"
      expected_release_manifest "$source_sha" "$compose_sha" "$cloud_digest" "$identity_digest" "$proxy_digest" > "$manifest_tmp"
      chmod 0600 "$manifest_tmp"
      mv -n -- "$manifest_tmp" "$release_dir/release.manifest"
      rm -f -- "$manifest_tmp"
    fi
    assert_staged_compose_release "$source_sha" "$compose_sha" "$cloud_digest" "$identity_digest" "$proxy_digest" >/dev/null
    rm -f -- "$upload_file"
    return 0
  fi
  temp_dir="$(mktemp -d "$ROOT/releases/.${source_sha}.XXXXXXXX")"
  chmod 0700 "$temp_dir"
  install -m 0600 "$upload_file" "$temp_dir/docker-compose.cloud.yml"
  expected_release_manifest "$source_sha" "$compose_sha" "$cloud_digest" "$identity_digest" "$proxy_digest" > "$temp_dir/release.manifest"
  chmod 0600 "$temp_dir/release.manifest"
  [[ "$(sha256sum -- "$temp_dir/docker-compose.cloud.yml" | awk '{print $1}')" == "$compose_sha" ]] \
    || { rm -rf -- "$temp_dir"; die 'staged Compose copy failed its SHA256 check'; }
  mv -- "$temp_dir" "$release_dir"
  rm -f -- "$upload_file"
  assert_staged_compose_release "$source_sha" "$compose_sha" "$cloud_digest" "$identity_digest" "$proxy_digest" >/dev/null
}
