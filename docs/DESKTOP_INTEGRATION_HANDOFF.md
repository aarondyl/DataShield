# DataShield Desktop v0.1.0 集成交接

分支：`feat/desktop-app`。PR #16 必须保持 Draft；不得合并 main、部署 Cloud 或创建 Release。

## 当前已验证

| 范围 | 状态 | 证据 |
| --- | --- | --- |
| Tauri sidecar、动态 loopback、runtime token bridge | PASS（构建） | Windows CI run 37783096879（旧 HEAD） |
| 本地 Company/Product、Product Twin 基础读写 | PASS | Desktop build；Product Twin tests |
| Cloud→Local 缓存、离线状态、法规事件 | PASS | `test_local_regulation_cache.py`、`test_local_sync_http_e2e.py` |
| 手动 Tenant Agent scan 与 Finding 列表 | PASS | `test_tenant_agent.py` |
| Finding 详情 API | PASS | `test_tenant_findings_api.py`；Desktop 已接详情读取 |
| Remediation UI | NOT STARTED | 后端服务/测试已存在，Desktop 未接通 |
| Feedback / correction / reanalysis UI | NOT STARTED | 后端服务/测试已存在，Desktop 未接通 |
| Today UI | NOT STARTED | 后端 API 已存在，Desktop 为占位 |
| 网站/仓库原生选择入口 | NOT STARTED | Understanding API 已存在，Desktop 未接通 |
| 最新 HEAD Windows CI / Artifact | REQUIRED | 旧 run 不代表当前 HEAD |

## 安全不变量

- Renderer 只可调用 Rust `local_api_request`；不得读取 `runtime.json` 或 runtime token。
- Cloud 同步只能拉取公开法规 HTTPS 数据；不得上传 Product Twin、证据或 SQLite。
- Correction 必须经过 `PROPOSED → CONFIRMED → APPLIED`，Twin 为 append-only。
- Remediation approval 不等于执行或解决 Finding。

## 集成优先顺序

1. 通过 bridge 接入 Finding detail、Remediation、Feedback、Today 和 Understanding facade；复用后端现有 contracts，不能复制领域服务。
2. 每一页同时新增 zh-CN/en-US 词条并做键完整性检查。
3. 跑后端全量回归、Desktop build，再触发最终 Windows workflow。
4. 下载最终 Artifact，计算 SHA256；Windows 11 实机安装验证仍需人工完成。

## 发布边界

准备独立 Release workflow 可以进行；创建 `desktop-v0.1.0` Pre-release、上传资产和 Stable Release 均需用户明确批准。Tauri updater 在签名和更新元数据未验证前不得启用。
