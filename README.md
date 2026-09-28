# 🛡️ 数盾 DataShield

面向中小 App 开发者 / 网站主的**一站式数据合规自查与整改工具**，覆盖
GDPR（欧盟《通用数据保护条例》）、中国《数据安全法》《个人信息保护法》。
无需法律背景，10 分钟完成一次专业级合规自查。

> ⚠️ 本工具由规则引擎与公开法条生成自查结果，仅供参考，不构成法律意见。

## ✨ 功能一览

| 模块 | 说明 |
| --- | --- |
| 📄 文档智能分析 | 上传项目计划书（txt/md/docx/pdf），AI 或规则自动预填问卷 |
| 📝 合规自查问卷 | 六大模块 20+ 问题、动态追问、六大行业预设一键加载 |
| ⚖️ 规则引擎 | 35 条合规规则，纯 Python if-else，逻辑透明可审计 |
| 📊 合规仪表盘 | 七维度雷达图、风险分布、维度得分、处罚案例联动警示 |
| 🗺️ 整改路线图 | 自动生成 7/30/90 天整改计划，可勾选进度 |
| 📑 合规报告 | 总分 + 评级，Markdown 报告一键导出 |
| 🛡️ 隐私政策生成 | 按问卷答案自动生成隐私政策初稿（可选 AI 润色） |
| 🔍 隐私政策体检 | 粘贴现有政策，检查 12 项法定必备要素（可选 AI 复核） |
| 📈 历史趋势 | 每次评估自动存档，多次得分趋势对比 |
| 📖 法条与案例 | 59 组法条摘要（可搜索）+ 16 个真实处罚案例 |

## 🚀 快速开始

```bash
git clone https://github.com/aarondyl/DataShield.git
cd DataShield
pip install -r requirements.txt
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`。Windows 用户也可以直接双击 `启动数盾.bat`。

## 🤖 启用 AI 功能（可选）

不配置也能完整运行（纯规则模式）。配置后解锁：AI 文档分析、AI 详细解释、隐私政策 AI 润色与复核。

方式一：复制 `config.example.py` 为 `config.py`，填入 Key：

```python
API_KEY = "sk-你的key"          # https://platform.deepseek.com/ 创建
MODEL = "deepseek-v4.1-flash"   # 可按平台实际模型名调整
```

方式二：环境变量（优先级更高）：

```bash
export DEEPSEEK_API_KEY="sk-你的key"     # Windows PowerShell: $env:DEEPSEEK_API_KEY="..."
```

方式三：Streamlit Cloud 部署时，在应用的 **Settings → Secrets** 中配置：

```toml
DEEPSEEK_API_KEY = "sk-你的key"
```

任何 AI 调用失败（无网络、Key 无效、超时）都会自动降级为内置模板/算法，应用绝不报错中断。

## ☁️ 部署到 Streamlit Cloud

1. Fork / 克隆本仓库到你的 GitHub 账号；
2. 打开 [share.streamlit.io](https://share.streamlit.io)，选择该仓库，入口文件填 `app.py`；
3. （可选）在 Secrets 中配置 `DEEPSEEK_API_KEY`；
4. Deploy，即可获得公开访问的网页版。

## 📁 项目结构

```
DataShield/
├── app.py                # Streamlit 主入口（10 个页面）
├── questionnaire.py      # 问卷定义（六模块 + 动态追问）
├── rules.py              # 合规规则引擎（核心：35 条规则、七维度评分）
├── regulations_data.py   # 法条引用数据库（个保法/数安法/GDPR 24 组）
├── cases_data.py         # 真实处罚案例库
├── presets.py            # 行业预设画像
├── doc_analyzer.py       # 文档上传解析与自动预填（AI/关键词双模式）
├── policy_generator.py   # 隐私政策生成器
├── policy_checker.py     # 隐私政策 12 要素体检
├── roadmap.py            # 整改路线图（7/30/90 天）
├── history.py            # 历史记录（本地 JSON）
├── charts.py             # 可视化图表（plotly）
├── report.py             # 评分与 Markdown 报告导出
├── llm_explainer.py      # LLM 模块（可选，全链路降级）
├── config.example.py     # 配置模板（复制为 config.py 使用）
├── requirements.txt
├── 启动数盾.bat           # Windows 一键启动
└── README.md
```

## 🧮 评分规则

总分 100 起始：命中 🔴 高风险 -15、🟡 中风险 -8、🟢 低风险 -3，下限 0 分。
评级：90+ 优秀 / 75-89 良好 / 60-74 待改进 / <60 高风险。
七个维度按同一规则独立计分，形成雷达图。

## 📄 License

MIT
