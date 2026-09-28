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

## 架构

```text
React + TypeScript
        │
        ▼
FastAPI ── 确定性规则引擎（问卷、评分、报告、隐私政策）
        │
        ├── LangGraph Agent（影响判断、证据验证、行动规划）
        ├── RAG（法规切片、Embedding、Top-K 检索）
        └── PostgreSQL + pgvector（本地开发可使用 SQLite）
```

仓库现在只有一套应用：

```text
DataShield/
├── frontend/              # React + Vite + TypeScript
├── backend/
│   ├── app/api/           # REST API
│   ├── app/agents/        # LangGraph 工作流
│   ├── app/compliance/    # 原 DataShield 规则、评分、报告和政策能力
│   ├── app/rag/           # 法规入库与检索
│   ├── app/models/        # SQLAlchemy 模型
│   └── tests/             # 后端自动化测试
├── docker-compose.yml     # 应用 + PostgreSQL/pgvector
└── 启动DataShield.bat      # Windows 本地开发启动器
```

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
pip install -r requirements.txt
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

## License

MIT
