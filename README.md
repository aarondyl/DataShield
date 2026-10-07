# DataShield

DataShield 是面向出海企业的数据合规分析与整改平台。新版将原有的规则自查工具与企业级法规影响分析架构合并为一套产品：React 前端、FastAPI 后端、LangGraph Agent、RAG 法规检索以及 PostgreSQL/pgvector 数据层。

> 本工具输出仅供合规工作参考，不构成法律意见。仓库中的预置法规内容带有 `[DEMO SUMMARY]` 标记，生产使用前应替换为经过核验的官方法规文本。

## 核心能力

- 企业与产品档案：维护企业、目标市场、产品及数据处理属性。
- 合规自查：六大问卷模块、35 条确定性规则、七维度评分和历史记录。
- 整改路线图：按高、中、低风险生成 7/30/90 天整改建议。
- 法规影响分析：通过 RAG + LangGraph 判断适用法规、受影响产品、风险与证据。
- 法规库：预置 GDPR、《个人信息保护法》《数据安全法》，支持上传法规文档。
- 隐私政策工具：根据评估答案生成初稿，检查现有政策的 12 项法定要素。
- 文档预填：根据产品说明或需求文档生成合规问卷预填建议。
- 账户体系与版本：邮箱+密码注册/登录（PBKDF2 哈希入库、HttpOnly cookie 会话），Demo / Developer / Enterprise 三个版本，保留免注册演示入口。
- 全站中英文切换：基于 react-i18next，Landing 顶栏与工作台侧边栏均有语言切换器。
- 桌面应用：Electron 壳内嵌 PyInstaller 打包的后端，Windows 一键安装，无需 Python 环境。

## 架构

```text
React + TypeScript（react-i18next 全站中英文）
        │
        ▼
FastAPI ── 确定性规则引擎（问卷、评分、报告、隐私政策）
        │
        ├── 账户认证（/v1/auth：邮箱+密码、PBKDF2 哈希、HttpOnly 会话）
        ├── LangGraph Agent（影响判断、证据验证、行动规划）
        ├── RAG（法规切片、Embedding、Top-K 检索）
        └── PostgreSQL + pgvector（本地开发可使用 SQLite）

桌面封装：Electron + PyInstaller 内嵌后端（desktop/，数据存 %APPDATA%/datashield-desktop）
```

仓库现在只有一套应用：

```text
DataShield/
├── api/index.py           # Vercel FastAPI Function 入口
├── frontend/              # React + Vite + TypeScript（含 src/i18n 中英文文案）
├── backend/
│   ├── app/api/           # REST API（含 /v1/auth 账户认证）
│   ├── app/agents/        # LangGraph 工作流
│   ├── app/compliance/    # 原 DataShield 规则、评分、报告和政策能力
│   ├── app/rag/           # 法规入库与检索
│   ├── app/models/        # SQLAlchemy 模型
│   └── tests/             # 后端自动化测试
├── desktop/               # Electron 桌面壳（内嵌 PyInstaller 后端）
├── docker-compose.yml     # 应用 + PostgreSQL/pgvector
└── 启动DataShield.bat      # Windows 本地开发启动器
```

## 账户体系

- 注册 / 登录：邮箱 + 密码，端点 `POST /api/v1/auth/register|login`；密码以 PBKDF2-HMAC-SHA256 哈希入库，会话使用 HttpOnly cookie。
- 其他端点：`POST /api/v1/auth/logout`、`GET /api/v1/auth/me`、`POST /api/v1/auth/verify-email`（邮箱验证码）。
- 免注册演示：`POST /api/v1/evaluation/demo` 保留演示入口，不注册也能进入工作区。
- 邮件预留窗口：默认 `MAILER_PROVIDER=console` 只把验证码打进后端日志，后续可扩展 `smtp` / `http` 真实发信；`AUTH_REQUIRE_EMAIL_VERIFY=true` 时注册流程开启邮箱验证。
- 账户数据落在同一个数据库：默认 SQLite 本地库，切换 PostgreSQL 改 `DATABASE_URL` 即可。

## 中英文切换与站点页面

- 全站中英文切换：基于 react-i18next，语言切换器位于 Landing 顶栏和工作台侧边栏；语言偏好存 localStorage（key：`datashield.lang`）。新增或修改文案的规范见 `frontend/src/i18n/README.md`。
- 新页面：`/features` 六大功能页、`/plans` 版本对比页（Demo / Developer / Enterprise）。
- 工作台内置法规库：`/app/regulations` 可全文查阅 GDPR、《个人信息保护法》《数据安全法》，支持条文展开与双语检索（`POST /api/v1/legal-search`）。

## 管理后台

- 入口 `/admin`，用管理员密钥（环境变量 `ADMIN_API_KEY`）登录；未配置该变量时管理 API 全部返回 503。
- 能力：总览统计、用户管理（禁用/启用/重置密码，禁用即吊销会话）、企业工作区浏览、法规库重置（`POST /api/v1/admin/regulations/reseed` 恢复三部法规初始状态）、清空演示数据（`POST /api/v1/admin/demo/reset`）。
- 所有管理请求需带请求头 `X-Admin-Key`；密钥只存在于服务端环境变量，不下发到普通用户。

## Vercel + Neon 部署

仓库已经按一个 Vercel 项目配置好：Vercel 构建 React 后由 `api/index.py` 中的 FastAPI 应用统一提供页面和 `/api/*`。前端与 API 同域，不需要额外设置 CORS。

1. 在 Vercel 选择 **Add New → Project**，导入 GitHub 仓库 `aarondyl/DataShield`。
2. Framework Preset 选择 **Other**，Root Directory 保持仓库根目录；构建命令和输出目录会自动读取 `vercel.json`。
3. 在项目的 **Storage** 页添加 Neon Postgres，并连接 Production（也可以同时连接 Preview）。Neon 集成会自动注入 `DATABASE_URL`。
4. 在 **Settings → Environment Variables** 添加下表中的变量，然后重新部署。

| 变量 | 建议值 | 是否必需 |
| --- | --- | --- |
| `DATABASE_URL` | Neon 集成自动提供的 pooled URL | 是 |
| `RUN_SEED` | `true` | 否，默认会初始化演示法规与公司 |
| `LLM_PROVIDER` | `mock`；启用真实模型时改为 `api` | 否 |
| `EMBEDDING_PROVIDER` | `local` | 否，先用于免费演示 |
| `LLM_API_KEY` | API 密钥 | `LLM_PROVIDER=api` 时设置 |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | 可选 |
| `LLM_MODEL` | `deepseek-chat` | 可选 |

首次请求会自动启用 Neon 的 `vector` 扩展、创建表并写入演示数据，因此不需要在 Vercel 上单独运行迁移。Neon 免费实例休眠后的首次访问可能有数秒冷启动。尚未连接 Neon 时，Vercel 会使用 `/tmp` 下的临时 SQLite 演示库；数据可能随函数重启而清空，接入 `DATABASE_URL` 后即切换为持久存储。

部署成功后可在 Vercel 的 **Settings → Domains** 添加从阿里云购买的域名，再到阿里云 DNS 按 Vercel 显示的记录添加 A 或 CNAME 解析。域名仍由阿里云管理，无需转移注册商。

## Docker 一键运行

需要 Docker Desktop：

```bash
docker compose up --build
```

打开 <http://localhost:8000>。生产镜像会先构建 React 前端，再由 FastAPI 从同一端口提供网页和 API。

默认使用离线 `mock` LLM 和本地 Embedding，可完整体验流程。启用 DeepSeek：

```bash
LLM_PROVIDER=api LLM_API_KEY=你的密钥 docker compose up --build
```

## 本地开发

后端使用 Python 3.12：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
# 若本机没有 PostgreSQL，将 .env 中 DATABASE_URL 改为 sqlite:///./datashield.db
uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

打开 <http://localhost:5173>。Vite 会把 `/api` 请求代理到 `http://localhost:8000`。

## 桌面应用

`desktop/` 目录是 Electron 壳：窗口与进程由 Electron 管理，FastAPI 后端以 PyInstaller 打包内嵌分发（用户无需安装 Python），前端静态文件由内嵌后端同源托管（`http://127.0.0.1:18321/`）。

桌面运行时安全模型（对齐 Desktop Runtime 规范）：

- 后端只绑定 `127.0.0.1`；每次启动由 Electron 生成随机 runtime token，经环境变量传给后端、经 IPC 传给界面，所有 `/api/*` 请求（除 `/api/health`）必须携带，防止同机其他进程或网页盗用本地 API。
- 数据集中存 `%APPDATA%/DataShield`（SQLite、日志、法规缓存）；旧版 `%APPDATA%/datashield-desktop` 数据首次启动自动迁移。
- 启动时自动执行 `alembic upgrade head` 迁移；迁移前自动备份数据库（保留最近 3 份），失败自动回滚并把错误写入 `logs/migration-error.log`。

开发模式（一条命令拉起本机后端、Vite 和 Electron）：

```bash
cd desktop
npm install
npm run dev
```

打包 NSIS 安装包：

```bash
cd desktop
npm run dist
```

产出 `desktop/release/DataShield Setup 0.1.0.exe`（约 193MB，内嵌 PyInstaller 后端 + 前端静态文件）。Windows 非管理员环境打包需先处理 winCodeSign 的 7za wrapper，详见 `desktop/README.md`。

## 测试

```bash
cd backend && python -m pytest tests -q
cd ../frontend && npm run build
```

## 主要 API

```text
GET  /api/health
GET/POST/PUT /api/companies
GET/POST/PUT /api/products
GET/POST     /api/regulations
GET/POST     /api/analysis
GET          /api/actions

GET      /api/compliance/questionnaire
GET/POST /api/compliance/assessments
POST     /api/compliance/documents/analyze
POST     /api/compliance/policy/generate
POST     /api/compliance/policy/check

POST /api/v1/auth/register|login|logout|verify-email
GET  /api/v1/auth/me
POST /api/v1/evaluation/demo   # 免注册演示入口
```

## 配置

后端读取 `backend/.env` 或环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./datashield.db` | SQLAlchemy 数据库地址 |
| `LLM_PROVIDER` | `mock` | `mock` 离线演示；`api` 调用真实模型 |
| `LLM_API_KEY` | 空 | OpenAI 兼容 API 密钥 |
| `LLM_BASE_URL` | DeepSeek API | OpenAI 兼容接口地址 |
| `LLM_MODEL` | `deepseek-chat` | 模型名称 |
| `EMBEDDING_PROVIDER` | `local` | `local` 哈希向量；`api` 远程 Embedding |
| `RUN_SEED` | `true` | 空数据库启动时写入演示数据 |
| `MAILER_PROVIDER` | `console` | 邮件通道：`console` 仅把验证码打进日志，可扩展 `smtp` / `http` 真实发信 |
| `AUTH_REQUIRE_EMAIL_VERIFY` | `false` | 注册后是否要求邮箱验证码验证 |
| `DESKTOP_MODE` | `false` | 桌面模式（Electron 内嵌后端）：放宽 Origin 校验、cookie 不带 `secure` |
| `ADMIN_API_KEY` | 空 | 管理后台密钥；为空时 `/api/v1/admin/*` 全部 503 |
| `UNDERSTANDING_API_KEY` | 空 | 产品理解（网站/仓库分析）服务端凭证；注意经 `os.getenv` 读取，须为真实进程环境变量（systemd 用 `EnvironmentFile` 注入），否则相关接口 503 |

## License

MIT
