# RegPilot

**RegPilot — 面向出海企业的法规影响分析与合规行动 Agent**

用户录入企业和产品信息、选择或上传法规，系统通过 RAG + LangGraph Agent 分析：
法规是否与企业相关、哪些产品受影响、风险等级、判断依据、对应条款，以及企业接下来应采取的行动。

第一版聚焦 **中国企业 + 欧盟数据合规场景**，预置 GDPR、中国《个人信息保护法》《数据安全法》核心条款。

> ⚠️ 预置法规条款为按通行解读编写的摘要，均以 `[DEMO SUMMARY]` 标记。
> 真实部署必须替换为经过核验的官方法规文本。本工具输出仅供参考，不构成法律意见。

## 架构

```
React (Vite+TS+Tailwind)  →  FastAPI  →  LangGraph Agent  →  LLM (OpenAI 兼容)
                                ↓              ↓
                          PostgreSQL      RAG 检索（pgvector Top-K）
                          业务数据        法规条款 embedding
```

LangGraph workflow：

```
load_context → retrieve_regulations → impact_analysis → evidence_verification
             ↘（证据不足且重试<1 次，回 impact_analysis）→ action_planning → save_result
```

## 快速开始

### 方式一：Docker Compose（推荐，PostgreSQL + pgvector）

```bash
cd regpilot
cp backend/.env.example backend/.env   # 按需填写 LLM_API_KEY 等
docker compose up --build
```

后端 http://localhost:8000 （自动建表、自动写入种子数据）。

### 方式二：本地开发（无需 Docker，SQLite 降级）

```bash
cd regpilot/backend
pip install -r requirements.txt
uvicorn app.main:app --reload          # 附带 .env 默认 sqlite + mock + local，开箱即用
```

前端：

```bash
cd regpilot/frontend
npm install
npm run dev                            # http://localhost:5173，/api 已代理到 8000
```

## 配置（backend/.env）

| 变量 | 说明 |
| --- | --- |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | OpenAI 兼容接口（DeepSeek 填 `https://api.deepseek.com/v1`）。留空时 Agent 节点降级运行并明确标注，服务不崩溃 |
| `LLM_PROVIDER` | `api` 真实调用；`mock` 离线确定性输出（测试/无 Key 演示全流程） |
| `EMBEDDING_PROVIDER` | `api` OpenAI 兼容 embeddings；`local` 内置哈希向量（384 维，离线可用） |
| `EMBEDDING_DIM` | 向量维度，默认 384 |
| `DATABASE_URL` | Docker：`postgresql+psycopg://regpilot:regpilot@postgres:5432/regpilot`；本地降级：`sqlite:///./regpilot.db` |
| `RUN_SEED` | 启动时写入种子数据（库为空时） |

## Demo 流程（种子数据已预置）

打开 http://localhost:5173 → Dashboard 可看到 **ABC Technology**（中国消费电子，目标市场 Germany/France）→
Analyze 页选择该企业及产品 **SmartWatch X1**（采集健康数据、跨境传输）→ 点击 **Analyze Impact** →
报告页展示 Risk Level（high）、Relevant（YES）、Affected Areas、Evidence（GDPR 第9条、个保法第29/38条等，含原文与 source_url）、Recommended Actions（分优先级与责任部门）。

## 测试

```bash
cd regpilot/backend
python -m pytest tests/ -q     # 37 例：chunking / embeddings / retrieval / agents / api
cd ../frontend && npm run build
```

## API 一览

```
GET  /api/health
POST /api/companies        GET /api/companies        GET/PUT /api/companies/{id}
POST /api/products         GET /api/products         GET/PUT /api/products/{id}
GET  /api/regulations      GET /api/regulations/{id} POST    /api/regulations/upload
POST /api/analysis         GET /api/analysis         GET     /api/analysis/{id}
GET  /api/actions
```

## 目录结构

```
regpilot/
├── frontend/            # Vite + React + TS + Tailwind（6 页面）
├── backend/
│   ├── app/
│   │   ├── api/         # companies/products/regulations/analysis/actions/health
│   │   ├── agents/      # LangGraph：state/graph/retrieval/impact/evidence/action
│   │   ├── rag/         # embeddings/chunking/ingestion/retrieval（pgvector + 本地降级）
│   │   ├── models/ schemas/ db/ core/ services/
│   ├── alembic/         # 初始迁移（pg 下建 vector 扩展与列，sqlite 降级 JSON）
│   ├── tests/           # pytest 37 例
│   ├── Dockerfile  requirements.txt  .env.example
├── docker-compose.yml   # pgvector/pgvector:pg16 + backend
└── README.md
```

## 说明与边界

- 首期不做：全球法规爬虫、实时监管、认证/多租户、Redis/Kafka/Celery 等（见需求文档）。
- `chat_threads` / `chat_messages` / `agent_memories` 为预留表，供后续扩展。
- 所有重要结论必须附带检索到的法规 Evidence；Evidence Node 逐条校验真实性，
  证据不足时标记 `relevant=null, confidence=low`，不强行得出高风险结论。
