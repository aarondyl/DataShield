#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{path::PathBuf, sync::Mutex, time::Duration};

use reqwest::Method;
use serde::{Deserialize, Serialize};
use tauri::{Manager, RunEvent, State};
use tauri_plugin_shell::{process::CommandChild, ShellExt};

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

fn valid_loopback_url(url: &str) -> bool {
    let Some(host_port) = url.strip_prefix("http://127.0.0.1:") else {
        return false;
    };
    host_port.parse::<u16>().is_ok_and(|port| port > 0)
}

fn valid_api_path(path: &str) -> bool {
    path.starts_with("/api/")
        && !path.starts_with("/api/v1/local-repositories/grant")
        && !path.split('?').next().unwrap_or("").contains('%')
        && !path.contains("..")
        && !path.contains("://")
        && !path.contains('\\')
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
            .timeout(Duration::from_secs(2))
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
    let mut builder = state
        .client
        .request(method, format!("{}{}", descriptor.base_url, request.path))
        .header("X-Runtime-Token", descriptor.runtime_token);
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
        return Err(format!("本地智能体请求失败（{}）", status.as_u16()));
    }
    Ok(body)
}

fn start_sidecar(app: &tauri::AppHandle, state: &DesktopState) -> Result<(), String> {
    let command = app
        .shell()
        .sidecar("datashield-local")
        .map_err(|_| "未找到已打包的本地智能体 sidecar".to_string())?;
    let (_events, child) = command
        .env("RUNTIME_MODE", "local")
        .env("RUN_SEED", "false")
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
            .timeout(Duration::from_secs(60))
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
            select_repository
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
                // Windows force termination skips Python's finally block.
                // Remove credentials only when they belong to this instance.
                if let Ok(path) = runtime_descriptor_path() {
                    if let Ok(raw) = std::fs::read_to_string(&path) {
                        if let Ok(descriptor) = serde_json::from_str::<RuntimeDescriptor>(&raw) {
                            let expected_pid = app.state::<DesktopState>()
                                .expected_sidecar_pid.lock().ok().and_then(|pid| *pid);
                            if expected_pid == Some(descriptor.pid) {
                                let _ = std::fs::remove_file(path);
                            }
                        }
                    }
                }
            }
        });
}

#[cfg(test)]
mod tests {
    use super::{valid_api_path, valid_loopback_url, valid_method};
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
        assert!(!valid_loopback_url("http://127.0.0.1:0"));
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
}
