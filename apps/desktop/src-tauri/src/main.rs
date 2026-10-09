#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{fs, path::PathBuf, sync::Mutex, time::Duration};

#[cfg(windows)]
use keyring::Entry;
use reqwest::Method;
use serde::{Deserialize, Serialize};
use tauri::{Manager, RunEvent, State};
use tauri_plugin_shell::{process::CommandChild, ShellExt};

const AI_CREDENTIAL_SERVICE: &str = "com.datashield.desktop";
const AI_CREDENTIAL_USER: &str = "local-ai-api-key";
const IDENTITY_CREDENTIAL_SERVICE: &str = "com.datashield.desktop.identity";

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct AiProviderConfig {
    provider: String,
    base_url: String,
    model: String,
    cloud_consent: bool,
}

impl Default for AiProviderConfig {
    fn default() -> Self {
        Self {
            provider: "mock".into(),
            base_url: "https://api.deepseek.com".into(),
            model: "deepseek-flash".into(),
            cloud_consent: false,
        }
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct AiProviderUpdate {
    provider: String,
    base_url: String,
    model: String,
    api_key: Option<String>,
    cloud_consent: bool,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct AiProviderView {
    provider: String,
    base_url: String,
    model: String,
    cloud_consent: bool,
    key_configured: bool,
}

#[derive(Clone, Deserialize)]
struct RuntimeDescriptor {
    base_url: String,
    runtime_token: String,
    pid: u32,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct LocalApiRequest {
    path: String,
    method: String,
    body: Option<serde_json::Value>,
}

#[derive(Serialize)]
struct RuntimeHealth {
    ok: bool,
    message: Option<String>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct IdentityAuthInput {
    base_url: String,
    email: String,
    password: String,
    name: Option<String>,
    organization_name: Option<String>,
    edition: Option<String>,
    device_name: Option<String>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct IdentityVerificationInput {
    base_url: String,
    email: String,
    code: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct IdentityResetRequestInput {
    base_url: String,
    email: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct IdentityResetConfirmInput {
    base_url: String,
    email: String,
    code: String,
    new_password: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct IdentityEndpointInput {
    base_url: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct IdentityOrganizationInput {
    base_url: String,
    organization_id: i64,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct IdentityInvitationInput {
    base_url: String,
    organization_id: i64,
    email: String,
    role: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct IdentityAcceptInvitationInput {
    base_url: String,
    code: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct IdentityMemberActionInput {
    base_url: String,
    organization_id: i64,
    user_id: i64,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct IdentityMemberRoleInput {
    base_url: String,
    organization_id: i64,
    user_id: i64,
    role: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct IdentitySessionActionInput {
    base_url: String,
    session_id: i64,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct IdentityAuthView {
    user_id: Option<i64>,
    email: String,
    name: Option<String>,
    email_verified: bool,
    organization: Option<serde_json::Value>,
    verification_required: bool,
}

struct DesktopState {
    client: reqwest::Client,
    descriptor: Mutex<Option<RuntimeDescriptor>>,
    expected_sidecar_pid: Mutex<Option<u32>>,
    child: Mutex<Option<CommandChild>>,
}

fn runtime_descriptor_path() -> Result<PathBuf, String> {
    let data_dir = if cfg!(target_os = "windows") {
        dirs_next::data_local_dir()
    } else {
        dirs_next::data_dir()
    }
    .ok_or_else(|| "无法定位当前用户的数据目录".to_string())?;
    Ok(data_dir.join("DataShield").join("runtime.json"))
}

fn app_data_dir() -> Result<PathBuf, String> {
    let base = if cfg!(target_os = "windows") {
        dirs_next::data_local_dir()
    } else {
        dirs_next::data_dir()
    }
    .ok_or_else(|| "无法定位当前用户的数据目录".to_string())?;
    Ok(base.join("DataShield"))
}

fn ai_config_path() -> Result<PathBuf, String> {
    Ok(app_data_dir()?.join("ai-provider.json"))
}

fn read_ai_config() -> AiProviderConfig {
    ai_config_path()
        .ok()
        .and_then(|path| fs::read(path).ok())
        .and_then(|bytes| serde_json::from_slice(&bytes).ok())
        .unwrap_or_default()
}

#[cfg(windows)]
fn credential_entry() -> Result<Entry, String> {
    Entry::new(AI_CREDENTIAL_SERVICE, AI_CREDENTIAL_USER)
        .map_err(|_| "KEYSTORE_UNAVAILABLE".to_string())
}

#[cfg(windows)]
fn identity_credential_entry(name: &str) -> Result<Entry, String> {
    Entry::new(IDENTITY_CREDENTIAL_SERVICE, name).map_err(|_| "KEYSTORE_UNAVAILABLE".to_string())
}

#[cfg(windows)]
fn store_identity_secret(name: &str, value: &str) -> Result<(), String> {
    identity_credential_entry(name)?
        .set_password(value)
        .map_err(|_| "IDENTITY_CREDENTIAL_SAVE_FAILED".into())
}

#[cfg(not(windows))]
fn store_identity_secret(_name: &str, _value: &str) -> Result<(), String> {
    Err("IDENTITY_CREDENTIAL_STORE_UNSUPPORTED".into())
}

#[cfg(windows)]
fn read_identity_secret(name: &str) -> Result<String, String> {
    identity_credential_entry(name)?
        .get_password()
        .map_err(|_| "IDENTITY_SESSION_MISSING".into())
}

#[cfg(not(windows))]
fn read_identity_secret(_name: &str) -> Result<String, String> {
    Err("IDENTITY_CREDENTIAL_STORE_UNSUPPORTED".into())
}

#[cfg(windows)]
fn delete_identity_secret(name: &str) -> Result<(), String> {
    match identity_credential_entry(name)?.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(_) => Err("IDENTITY_CREDENTIAL_DELETE_FAILED".into()),
    }
}

#[cfg(not(windows))]
fn delete_identity_secret(_name: &str) -> Result<(), String> {
    Err("IDENTITY_CREDENTIAL_STORE_UNSUPPORTED".into())
}

fn store_identity_tokens(value: &serde_json::Value) -> Result<(), String> {
    let access = value
        .get("access_token")
        .and_then(|v| v.as_str())
        .ok_or("IDENTITY_RESPONSE_INVALID")?;
    let refresh = value
        .get("refresh_token")
        .and_then(|v| v.as_str())
        .ok_or("IDENTITY_RESPONSE_INVALID")?;
    store_identity_secret("access-token", access)?;
    if let Err(error) = store_identity_secret("refresh-token", refresh) {
        let _ = delete_identity_secret("access-token");
        return Err(error);
    }
    Ok(())
}

fn clear_identity_tokens() -> Result<(), String> {
    let access_result = delete_identity_secret("access-token");
    let refresh_result = delete_identity_secret("refresh-token");
    access_result.and(refresh_result)
}

#[cfg(not(windows))]
fn get_stored_key() -> Result<String, String> {
    Err("KEYSTORE_WINDOWS_ONLY".into())
}

#[cfg(windows)]
fn get_stored_key() -> Result<String, String> {
    credential_entry()?
        .get_password()
        .map_err(|_| "KEY_NOT_SAVED".into())
}

#[cfg(not(windows))]
fn save_stored_key(_key: &str) -> Result<(), String> {
    Err("KEYSTORE_WINDOWS_ONLY".into())
}

#[cfg(windows)]
fn save_stored_key(key: &str) -> Result<(), String> {
    credential_entry()?
        .set_password(key)
        .map_err(|_| "KEY_SAVE_FAILED".into())
}

#[cfg(not(windows))]
fn remove_stored_key() -> Result<(), String> {
    Err("KEYSTORE_WINDOWS_ONLY".into())
}

#[cfg(windows)]
fn remove_stored_key() -> Result<(), String> {
    match credential_entry()?.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(_) => Err("KEY_DELETE_FAILED".into()),
    }
}

fn ai_provider_view(config: AiProviderConfig) -> AiProviderView {
    let key_configured = get_stored_key().is_ok();
    AiProviderView {
        provider: config.provider,
        base_url: config.base_url,
        model: config.model,
        cloud_consent: config.cloud_consent,
        key_configured,
    }
}

#[tauri::command]
fn get_ai_provider_config() -> AiProviderView {
    ai_provider_view(read_ai_config())
}

fn valid_ai_endpoint(provider: &str, base_url: &str) -> bool {
    match provider {
        "byok" => reqwest::Url::parse(base_url)
            .map(|url| {
                url.scheme() == "https"
                    && url.host().is_some()
                    && url.username().is_empty()
                    && url.password().is_none()
                    && url.query().is_none()
                    && url.fragment().is_none()
            })
            .unwrap_or(false),
        "ollama" => base_url == "http://127.0.0.1:11434/v1",
        "cloud" => reqwest::Url::parse(base_url)
            .map(|url| {
                url.scheme() == "https"
                    && url.host().is_some()
                    && url.username().is_empty()
                    && url.password().is_none()
                    && url.query().is_none()
                    && url.fragment().is_none()
            })
            .unwrap_or(false),
        "mock" => true,
        _ => false,
    }
}

#[tauri::command]
fn set_ai_provider_config(update: AiProviderUpdate) -> Result<AiProviderView, String> {
    let provider = update.provider.trim();
    let base_url = update.base_url.trim().trim_end_matches('/');
    let model = update.model.trim();
    if !valid_ai_endpoint(provider, base_url) {
        return Err("AI_ENDPOINT_INVALID".into());
    }
    if provider != "mock" && model.is_empty() {
        return Err("AI_MODEL_REQUIRED".into());
    }
    if matches!(provider, "byok" | "cloud") && !update.cloud_consent {
        return Err("AI_CONSENT_REQUIRED".into());
    }
    if provider == "cloud" && read_identity_secret("access-token").is_err() {
        return Err("IDENTITY_SESSION_MISSING".into());
    }

    let provided_key = update.api_key.unwrap_or_default();
    if provider == "byok" && !provided_key.is_empty() {
        save_stored_key(provided_key.trim())?;
    }
    if provider == "byok" && get_stored_key().is_err() {
        return Err("AI_KEY_REQUIRED".into());
    }
    if provider == "mock" {
        remove_stored_key()?;
    }

    let config = AiProviderConfig {
        provider: provider.to_string(),
        base_url: base_url.to_string(),
        model: model.to_string(),
        cloud_consent: update.cloud_consent,
    };
    let path = ai_config_path()?;
    fs::create_dir_all(path.parent().ok_or("AI_CONFIG_PATH_INVALID")?)
        .map_err(|_| "AI_CONFIG_DIRECTORY_FAILED".to_string())?;
    fs::write(
        &path,
        serde_json::to_vec(&config).map_err(|_| "AI_CONFIG_ENCODE_FAILED")?,
    )
    .map_err(|_| "AI_CONFIG_SAVE_FAILED".to_string())?;
    Ok(ai_provider_view(config))
}

#[tauri::command]
fn delete_ai_provider_key() -> Result<(), String> {
    remove_stored_key()
}

fn valid_loopback_url(url: &str) -> bool {
    let Some(host_port) = url.strip_prefix("http://127.0.0.1:") else {
        return false;
    };
    !host_port.is_empty() && host_port.parse::<u16>().is_ok()
}

fn valid_api_path(path: &str) -> bool {
    path.starts_with("/api/")
        && !path.starts_with("/api/v1/local-repositories/grant")
        && !path.split('?').next().unwrap_or("").contains('%')
        && !path.contains("..")
        && !path.contains("://")
        && !path.contains('\\')
}

fn valid_identity_endpoint(base_url: &str) -> bool {
    reqwest::Url::parse(base_url)
        .map(|url| {
            url.scheme() == "https"
                && url.host_str().is_some()
                && url.username().is_empty()
                && url.password().is_none()
                && url.query().is_none()
                && url.fragment().is_none()
        })
        .unwrap_or(false)
}

fn identity_url(base_url: &str, path: &str) -> Result<String, String> {
    let base = base_url.trim().trim_end_matches('/');
    if !valid_identity_endpoint(base) || !path.starts_with("/v1/") || path.contains("..") {
        return Err("IDENTITY_ENDPOINT_INVALID".into());
    }
    Ok(format!("{base}{path}"))
}

async fn identity_response(response: reqwest::Response) -> Result<serde_json::Value, String> {
    let status = response.status();
    let body = response
        .json::<serde_json::Value>()
        .await
        .unwrap_or_default();
    if !status.is_success() {
        let detail = body
            .get("detail")
            .and_then(|v| v.as_str())
            .unwrap_or("IDENTITY_REQUEST_FAILED");
        return Err(format!("{detail} (HTTP {})", status.as_u16()));
    }
    Ok(body)
}

fn identity_view(
    value: &serde_json::Value,
    verification_required: bool,
) -> Result<IdentityAuthView, String> {
    Ok(IdentityAuthView {
        user_id: value.get("user_id").and_then(|v| v.as_i64()),
        email: value
            .get("email")
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .to_owned(),
        name: value
            .get("name")
            .and_then(|v| v.as_str())
            .map(str::to_owned),
        email_verified: value
            .get("email_verified")
            .and_then(|v| v.as_bool())
            .unwrap_or(false),
        organization: value.get("organization").cloned(),
        verification_required,
    })
}

#[tauri::command]
async fn cloud_identity_register(
    input: IdentityAuthInput,
    state: State<'_, DesktopState>,
) -> Result<IdentityAuthView, String> {
    let url = identity_url(&input.base_url, "/v1/auth/register")?;
    let response = state
        .client
        .post(url)
        .json(&serde_json::json!({
            "email": input.email,
            "password": input.password,
            "name": input.name.unwrap_or_default(),
            "organization_name": input.organization_name.unwrap_or_default(),
            "edition": input.edition.unwrap_or_else(|| "developer".into()),
        }))
        .timeout(Duration::from_secs(20))
        .send()
        .await
        .map_err(|_| "IDENTITY_SERVICE_UNAVAILABLE".to_string())?;
    let value = identity_response(response).await?;
    if value.get("access_token").is_some() {
        store_identity_tokens(&value)?;
    }
    identity_view(
        &value,
        value
            .get("verification_required")
            .and_then(|v| v.as_bool())
            .unwrap_or(false),
    )
}

#[tauri::command]
async fn cloud_identity_verify_email(
    input: IdentityVerificationInput,
    state: State<'_, DesktopState>,
) -> Result<bool, String> {
    let url = identity_url(&input.base_url, "/v1/auth/verify-email")?;
    let response = state
        .client
        .post(url)
        .json(&serde_json::json!({"email": input.email, "code": input.code}))
        .timeout(Duration::from_secs(20))
        .send()
        .await
        .map_err(|_| "IDENTITY_SERVICE_UNAVAILABLE".to_string())?;
    let value = identity_response(response).await?;
    Ok(value
        .get("verified")
        .and_then(|v| v.as_bool())
        .unwrap_or(false))
}

#[tauri::command]
async fn cloud_identity_resend_verification(
    input: IdentityResetRequestInput,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    let url = identity_url(&input.base_url, "/v1/auth/verification/resend")?;
    let response = state
        .client
        .post(url)
        .json(&serde_json::json!({"email": input.email}))
        .timeout(Duration::from_secs(20))
        .send()
        .await
        .map_err(|_| "IDENTITY_SERVICE_UNAVAILABLE".to_string())?;
    identity_response(response).await.map(|_| ())
}

#[tauri::command]
async fn cloud_identity_password_reset_request(
    input: IdentityResetRequestInput,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    let url = identity_url(&input.base_url, "/v1/auth/password-reset/request")?;
    let response = state
        .client
        .post(url)
        .json(&serde_json::json!({"email": input.email}))
        .timeout(Duration::from_secs(20))
        .send()
        .await
        .map_err(|_| "IDENTITY_SERVICE_UNAVAILABLE".to_string())?;
    identity_response(response).await.map(|_| ())
}

#[tauri::command]
async fn cloud_identity_password_reset_confirm(
    input: IdentityResetConfirmInput,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    let url = identity_url(&input.base_url, "/v1/auth/password-reset/confirm")?;
    let response = state
        .client
        .post(url)
        .json(&serde_json::json!({
            "email": input.email,
            "code": input.code,
            "new_password": input.new_password,
        }))
        .timeout(Duration::from_secs(20))
        .send()
        .await
        .map_err(|_| "IDENTITY_SERVICE_UNAVAILABLE".to_string())?;
    identity_response(response).await.map(|_| ())
}

#[tauri::command]
async fn cloud_identity_login(
    input: IdentityAuthInput,
    state: State<'_, DesktopState>,
) -> Result<IdentityAuthView, String> {
    let url = identity_url(&input.base_url, "/v1/auth/login")?;
    let response = state
        .client
        .post(url)
        .json(&serde_json::json!({
            "email": input.email,
            "password": input.password,
            "device_name": input.device_name.unwrap_or_else(|| "DataShield Desktop".into()),
        }))
        .timeout(Duration::from_secs(20))
        .send()
        .await
        .map_err(|_| "IDENTITY_SERVICE_UNAVAILABLE".to_string())?;
    let value = identity_response(response).await?;
    store_identity_tokens(&value)?;
    identity_view(&value, false)
}

async fn identity_refresh(base_url: &str, state: &DesktopState) -> Result<(), String> {
    let refresh = read_identity_secret("refresh-token")?;
    let url = identity_url(base_url, "/v1/auth/refresh")?;
    let response = state
        .client
        .post(url)
        .json(&serde_json::json!({"refresh_token": refresh}))
        .timeout(Duration::from_secs(20))
        .send()
        .await
        .map_err(|_| "IDENTITY_SERVICE_UNAVAILABLE".to_string())?;
    let value = identity_response(response).await?;
    store_identity_tokens(&value)
}

async fn identity_authenticated_request(
    base_url: &str,
    path: &str,
    method: Method,
    body: Option<serde_json::Value>,
    state: &DesktopState,
) -> Result<serde_json::Value, String> {
    let url = identity_url(base_url, path)?;
    let access = read_identity_secret("access-token")?;
    let mut request = state
        .client
        .request(method.clone(), &url)
        .bearer_auth(access);
    if let Some(json) = body.clone() {
        request = request.json(&json);
    }
    let response = request
        .timeout(Duration::from_secs(20))
        .send()
        .await
        .map_err(|_| "IDENTITY_SERVICE_UNAVAILABLE".to_string())?;
    if response.status() == reqwest::StatusCode::UNAUTHORIZED {
        identity_refresh(base_url, state).await?;
        let access = read_identity_secret("access-token")?;
        let mut request = state.client.request(method, &url).bearer_auth(access);
        if let Some(json) = body {
            request = request.json(&json);
        }
        let response = request
            .timeout(Duration::from_secs(20))
            .send()
            .await
            .map_err(|_| "IDENTITY_SERVICE_UNAVAILABLE".to_string())?;
        return identity_response(response).await;
    }
    identity_response(response).await
}

#[tauri::command]
async fn cloud_identity_organizations(
    input: IdentityEndpointInput,
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    identity_authenticated_request(
        &input.base_url,
        "/v1/organizations",
        Method::GET,
        None,
        &state,
    )
    .await
}

#[tauri::command]
async fn cloud_identity_switch_organization(
    input: IdentityOrganizationInput,
    state: State<'_, DesktopState>,
) -> Result<IdentityAuthView, String> {
    let value = identity_authenticated_request(
        &input.base_url,
        &format!("/v1/organizations/{}/switch", input.organization_id),
        Method::POST,
        Some(serde_json::json!({})),
        &state,
    )
    .await?;
    store_identity_tokens(&value)?;
    identity_view(&value, false)
}

#[tauri::command]
async fn cloud_identity_members(
    input: IdentityOrganizationInput,
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    identity_authenticated_request(
        &input.base_url,
        &format!("/v1/organizations/{}/members", input.organization_id),
        Method::GET,
        None,
        &state,
    )
    .await
}

#[tauri::command]
async fn cloud_identity_invite(
    input: IdentityInvitationInput,
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    identity_authenticated_request(
        &input.base_url,
        &format!("/v1/organizations/{}/invitations", input.organization_id),
        Method::POST,
        Some(serde_json::json!({"email": input.email, "role": input.role})),
        &state,
    )
    .await
}

#[tauri::command]
async fn cloud_identity_accept_invitation(
    input: IdentityAcceptInvitationInput,
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    identity_authenticated_request(
        &input.base_url,
        "/v1/invitations/accept",
        Method::POST,
        Some(serde_json::json!({"code": input.code})),
        &state,
    )
    .await
}

#[tauri::command]
async fn cloud_identity_remove_member(
    input: IdentityMemberActionInput,
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    identity_authenticated_request(
        &input.base_url,
        &format!(
            "/v1/organizations/{}/members/{}",
            input.organization_id, input.user_id
        ),
        Method::DELETE,
        None,
        &state,
    )
    .await
}

#[tauri::command]
async fn cloud_identity_change_member_role(
    input: IdentityMemberRoleInput,
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    identity_authenticated_request(
        &input.base_url,
        &format!(
            "/v1/organizations/{}/members/{}",
            input.organization_id, input.user_id
        ),
        Method::PATCH,
        Some(serde_json::json!({"role": input.role})),
        &state,
    )
    .await
}

#[tauri::command]
async fn cloud_identity_sessions(
    input: IdentityEndpointInput,
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    identity_authenticated_request(
        &input.base_url,
        "/v1/auth/sessions",
        Method::GET,
        None,
        &state,
    )
    .await
}

#[tauri::command]
async fn cloud_identity_revoke_session(
    input: IdentitySessionActionInput,
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    identity_authenticated_request(
        &input.base_url,
        &format!("/v1/auth/sessions/{}", input.session_id),
        Method::DELETE,
        None,
        &state,
    )
    .await
}

#[tauri::command]
async fn cloud_identity_me(
    input: IdentityEndpointInput,
    state: State<'_, DesktopState>,
) -> Result<IdentityAuthView, String> {
    let url = identity_url(&input.base_url, "/v1/auth/me")?;
    let access = read_identity_secret("access-token")?;
    let response = state
        .client
        .get(&url)
        .bearer_auth(&access)
        .timeout(Duration::from_secs(20))
        .send()
        .await
        .map_err(|_| "IDENTITY_SERVICE_UNAVAILABLE".to_string())?;
    if response.status() == reqwest::StatusCode::UNAUTHORIZED {
        identity_refresh(&input.base_url, &state).await?;
        let access = read_identity_secret("access-token")?;
        let response = state
            .client
            .get(&url)
            .bearer_auth(access)
            .timeout(Duration::from_secs(20))
            .send()
            .await
            .map_err(|_| "IDENTITY_SERVICE_UNAVAILABLE".to_string())?;
        return identity_view(&identity_response(response).await?, false);
    }
    identity_view(&identity_response(response).await?, false)
}

#[tauri::command]
async fn cloud_identity_logout(
    input: IdentityEndpointInput,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    let result = match read_identity_secret("access-token") {
        Ok(access) => match identity_url(&input.base_url, "/v1/auth/logout") {
            Ok(url) => match state
                .client
                .post(url)
                .bearer_auth(access)
                .timeout(Duration::from_secs(20))
                .send()
                .await
            {
                Ok(response) => identity_response(response).await.map(|_| ()),
                Err(_) => Err("IDENTITY_SERVICE_UNAVAILABLE".to_string()),
            },
            Err(error) => Err(error),
        },
        Err(_) => Ok(()),
    };
    clear_identity_tokens()?;
    result
}

#[tauri::command]
async fn select_repository(state: State<'_, DesktopState>) -> Result<Option<String>, String> {
    #[cfg(windows)]
    {
        let selected =
            tauri::async_runtime::spawn_blocking(|| rfd::FileDialog::new().pick_folder())
                .await
                .map_err(|_| "无法打开文件夹选择器".to_string())?;
        let Some(path) = selected else {
            return Ok(None);
        };
        let descriptor = descriptor_from_state(&state).await?;
        let response = state
            .client
            .post(format!(
                "{}/api/v1/local-repositories/grant",
                descriptor.base_url
            ))
            .header("X-Runtime-Token", descriptor.runtime_token)
            .json(&serde_json::json!({"path": path.to_string_lossy()}))
            .send()
            .await
            .map_err(|_| "无法授权所选目录".to_string())?;
        if !response.status().is_success() {
            return Err("所选目录不允许扫描".to_string());
        }
        let value: serde_json::Value = response
            .json()
            .await
            .map_err(|_| "目录授权响应无效".to_string())?;
        Ok(value
            .get("path")
            .and_then(|v| v.as_str())
            .map(str::to_owned))
    }
    #[cfg(not(windows))]
    {
        let _ = state;
        Err("此预览版本的原生目录选择器仅支持 Windows".to_string())
    }
}

fn valid_method(method: &str) -> bool {
    matches!(method, "GET" | "POST" | "PUT" | "PATCH" | "DELETE")
}

async fn load_descriptor() -> Result<RuntimeDescriptor, String> {
    let path = runtime_descriptor_path()?;
    let raw = tokio::fs::read_to_string(path)
        .await
        .map_err(|_| "本地智能体尚未就绪".to_string())?;
    let descriptor: RuntimeDescriptor =
        serde_json::from_str(&raw).map_err(|_| "本地运行时描述无效".to_string())?;
    if !valid_loopback_url(&descriptor.base_url)
        || descriptor.runtime_token.is_empty()
        || descriptor.pid == 0
    {
        return Err("本地运行时描述不符合安全约束".to_string());
    }
    Ok(descriptor)
}

async fn descriptor_from_state(state: &DesktopState) -> Result<RuntimeDescriptor, String> {
    if let Some(value) = state
        .descriptor
        .lock()
        .map_err(|_| "运行时状态不可用")?
        .clone()
    {
        return Ok(value);
    }
    let descriptor = load_descriptor().await?;
    let expected_pid = *state
        .expected_sidecar_pid
        .lock()
        .map_err(|_| "运行时状态不可用")?;
    if expected_pid != Some(descriptor.pid) {
        return Err("本地运行时不属于当前 Desktop 进程".to_string());
    }
    *state.descriptor.lock().map_err(|_| "运行时状态不可用")? = Some(descriptor.clone());
    Ok(descriptor)
}

async fn wait_for_descriptor(state: &DesktopState) -> Result<(), String> {
    for _ in 0..80 {
        if let Ok(descriptor) = load_descriptor().await {
            let expected_pid = *state
                .expected_sidecar_pid
                .lock()
                .map_err(|_| "运行时状态不可用")?;
            if expected_pid == Some(descriptor.pid) {
                *state.descriptor.lock().map_err(|_| "运行时状态不可用")? = Some(descriptor);
                return Ok(());
            }
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
    Err("本地智能体启动超时".to_string())
}

#[tauri::command]
async fn runtime_health(state: State<'_, DesktopState>) -> Result<RuntimeHealth, String> {
    let descriptor = match descriptor_from_state(&state).await {
        Ok(value) => value,
        Err(message) => {
            return Ok(RuntimeHealth {
                ok: false,
                message: Some(message),
            });
        }
    };
    Ok(
        match state
            .client
            .get(format!("{}/api/health", descriptor.base_url))
            .send()
            .await
        {
            Ok(response) if response.status().is_success() => RuntimeHealth {
                ok: true,
                message: None,
            },
            _ => RuntimeHealth {
                ok: false,
                message: Some("本地智能体未响应".to_string()),
            },
        },
    )
}

#[tauri::command]
async fn local_api_request(
    request: LocalApiRequest,
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    if !valid_api_path(&request.path) {
        return Err("不允许的本地 API 路径".to_string());
    }
    if !valid_method(&request.method) {
        return Err("不允许的本地 API 方法".to_string());
    }
    let method = Method::from_bytes(request.method.as_bytes())
        .map_err(|_| "不支持的请求方法".to_string())?;
    let descriptor = descriptor_from_state(&state).await?;
    let cloud_ai = read_ai_config().provider == "cloud";
    let ai_request = request.path.starts_with("/api/v1/tenant-agent/analyze")
        || request.path.starts_with("/api/v1/ui/understanding/")
        || request.path.starts_with("/api/v1/feedback/")
        || request.path.starts_with("/api/v1/remediations/")
        || request.path.starts_with("/api/ai/provider/test");
    if cloud_ai && ai_request {
        identity_authenticated_request(
            &read_ai_config().base_url,
            "/v1/auth/me",
            Method::GET,
            None,
            &state,
        )
        .await?;
    }
    let mut builder = state
        .client
        .request(method, format!("{}{}", descriptor.base_url, request.path))
        .header("X-Runtime-Token", descriptor.runtime_token);
    if read_ai_config().provider == "cloud" {
        if let Ok(token) = read_identity_secret("access-token") {
            builder = builder.header("X-Cloud-Identity-Token", token);
        }
    }
    if let Some(body) = request.body {
        builder = builder.json(&body);
    }
    let response = builder
        .send()
        .await
        .map_err(|_| "本地智能体请求失败".to_string())?;
    let status = response.status();
    let body = response
        .json::<serde_json::Value>()
        .await
        .unwrap_or_else(|_| serde_json::json!({ "detail": "本地智能体返回了无效响应" }));
    if !status.is_success() {
        let detail = body
            .get("detail")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("本地智能体请求失败");
        return Err(format!("{}（HTTP {}）", detail, status.as_u16()));
    }
    Ok(body)
}

fn start_sidecar(app: &tauri::AppHandle, state: &DesktopState) -> Result<(), String> {
    let ai = read_ai_config();
    let mut command = app
        .shell()
        .sidecar("datashield-local")
        .map_err(|_| "未找到已打包的本地智能体 sidecar".to_string())?
        .env("RUNTIME_MODE", "local")
        .env("DESKTOP_MODE", "true")
        .env("RUN_SEED", "false")
        .env("LLM_API_KEY", "")
        .env("LLM_CLOUD_CONSENT", "false");
    match ai.provider.as_str() {
        "byok" => {
            command = command
                .env("DESKTOP_AI_MODE", "byok")
                .env("LLM_PROVIDER", "api")
                .env("LLM_BASE_URL", &ai.base_url)
                .env("LLM_MODEL", &ai.model)
                .env("LLM_CLOUD_CONSENT", ai.cloud_consent.to_string());
            #[cfg(windows)]
            {
                if let Ok(key) = get_stored_key() {
                    command = command.env("LLM_API_KEY", key);
                }
            }
        }
        "ollama" => {
            command = command
                .env("DESKTOP_AI_MODE", "local")
                .env("LLM_PROVIDER", "api")
                .env("LLM_BASE_URL", &ai.base_url)
                .env("LLM_MODEL", &ai.model);
        }
        "cloud" => {
            command = command
                .env("DESKTOP_AI_MODE", "cloud")
                .env("LLM_PROVIDER", "cloud")
                .env("LLM_BASE_URL", &ai.base_url)
                .env("LLM_MODEL", &ai.model)
                .env("LLM_CLOUD_CONSENT", ai.cloud_consent.to_string());
        }
        _ => command = command.env("DESKTOP_AI_MODE", "mock"),
    }
    let (_events, child) = command
        .spawn()
        .map_err(|_| "无法启动本地智能体 sidecar".to_string())?;
    *state
        .expected_sidecar_pid
        .lock()
        .map_err(|_| "运行时状态不可用")? = Some(child.pid());
    *state.child.lock().map_err(|_| "运行时状态不可用")? = Some(child);
    Ok(())
}

fn main() {
    let state = DesktopState {
        // Never forward the process-held runtime token through a redirect.
        client: reqwest::Client::builder()
            .redirect(reqwest::redirect::Policy::none())
            .build()
            .expect("Unable to initialize the local HTTP client"),
        descriptor: Mutex::new(None),
        expected_sidecar_pid: Mutex::new(None),
        child: Mutex::new(None),
    };
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(state)
        .setup(|app| {
            let state = app.state::<DesktopState>();
            start_sidecar(&app.handle(), &state).map_err(std::io::Error::other)?;
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let state = handle.state::<DesktopState>();
                let _ = wait_for_descriptor(&state).await;
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            runtime_health,
            local_api_request,
            select_repository,
            get_ai_provider_config,
            set_ai_provider_config,
            delete_ai_provider_key,
            cloud_identity_register,
            cloud_identity_verify_email,
            cloud_identity_resend_verification,
            cloud_identity_password_reset_request,
            cloud_identity_password_reset_confirm,
            cloud_identity_login,
            cloud_identity_me,
            cloud_identity_logout,
            cloud_identity_organizations,
            cloud_identity_switch_organization,
            cloud_identity_members,
            cloud_identity_invite,
            cloud_identity_accept_invitation,
            cloud_identity_remove_member,
            cloud_identity_change_member_role,
            cloud_identity_sessions,
            cloud_identity_revoke_session
        ])
        .build(tauri::generate_context!())
        .expect("启动 DataShield Desktop 失败")
        .run(|app, event| {
            if let RunEvent::ExitRequested { .. } = event {
                if let Some(mut child) = app
                    .state::<DesktopState>()
                    .child
                    .lock()
                    .ok()
                    .and_then(|mut item| item.take())
                {
                    let _ = child.kill();
                }
            }
        });
}

#[cfg(test)]
mod tests {
    use super::{
        identity_url, valid_api_path, valid_identity_endpoint, valid_loopback_url, valid_method,
    };
    #[test]
    fn renderer_has_no_shell_spawn_permission() {
        let capability: serde_json::Value =
            serde_json::from_str(include_str!("../capabilities/default.json")).unwrap();
        assert_eq!(
            capability["permissions"],
            serde_json::json!(["core:default"])
        );
    }
    #[test]
    fn only_loopback_runtime_urls_are_accepted() {
        assert!(valid_loopback_url("http://127.0.0.1:48327"));
        assert!(!valid_loopback_url("http://0.0.0.0:48327"));
        assert!(!valid_loopback_url("https://127.0.0.1:443"));
    }
    #[test]
    fn bridge_rejects_url_and_traversal_paths() {
        assert!(valid_api_path("/api/products"));
        assert!(!valid_api_path("https://example.com"));
        assert!(!valid_api_path("/api/../secret"));
        assert!(!valid_api_path("/api/v1/local-repositories/grant"));
        assert!(!valid_api_path("/api/v1/local-repositories/%67rant"));
    }
    #[test]
    fn bridge_only_allows_expected_http_methods() {
        assert!(valid_method("POST"));
        assert!(!valid_method("CONNECT"));
    }

    #[test]
    fn identity_bridge_requires_https_endpoint_and_fixed_api_paths() {
        assert!(valid_identity_endpoint(
            "https://api.datashield.ltd/identity"
        ));
        assert!(!valid_identity_endpoint(
            "http://api.datashield.ltd/identity"
        ));
        assert!(!valid_identity_endpoint("https://user:secret@example.test"));
        assert!(identity_url("https://api.datashield.ltd/identity", "/v1/auth/login").is_ok());
        assert!(identity_url("https://api.datashield.ltd/identity", "/v1/../private").is_err());
    }

    #[test]
    fn byok_requires_https_without_embedded_credentials_or_query() {
        assert!(super::valid_ai_endpoint("byok", "https://api.deepseek.com"));
        assert!(super::valid_ai_endpoint("byok", "https://example.test/v1"));
        assert!(!super::valid_ai_endpoint("byok", "http://example.test/v1"));
        assert!(!super::valid_ai_endpoint(
            "byok",
            "https://user:secret@example.test/v1"
        ));
        assert!(!super::valid_ai_endpoint(
            "byok",
            "https://example.test/v1?key=secret"
        ));
    }

    #[test]
    fn ollama_endpoint_is_confined_to_loopback() {
        assert!(super::valid_ai_endpoint(
            "ollama",
            "http://127.0.0.1:11434/v1"
        ));
        assert!(!super::valid_ai_endpoint(
            "ollama",
            "http://192.168.1.20:11434/v1"
        ));
    }
}
