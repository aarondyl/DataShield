# DataShield 收官任务档案（2026-10-08 02:00 继续执行）

> 用户要求：明早交付一份**可直接提交的赏心悦目的参赛作品**——前后端/UI/桌面软件全面设计验证、**所有按钮亲自点一遍**，最后产出一份**产品说明书**。这是最后机会，必须彻底。

## 环境坐标
- 代码：`D:\DataShield`（git main，最新提交 `afa78ca`）；工作目录就在此开发，分阶段 commit
- 本地服务：后端 :8000（env 需带 `ADMIN_API_KEY='DS-Admin-2026-ab17f3c9'` `UNDERSTANDING_API_KEY='VEtDGntf1-tNJvYCmeUqQbrx8_mVxkv4cnGUSBL26n0'`，DeepSeek api 模式在 backend/.env）；前端 Vite :5173。node 需 `export PATH="/c/Users/jiang/.local/node:$PATH"`
- 线上：http://123.57.252.25（阿里云 root 密码 `DataShield1001**`；部署助手 `deploy/ssh.py`（DS_PASS 环境变量传密码）；**大文件 SFTP 会被拦**，用 `MSYS2_ARG_CONV_EXCL='*' DS_PASS=... python deploy/upload_chunks.py pkg.bin /tmp/pkg.bin` 碎块上传；systemd 服务名 datashield，EnvironmentFile=/opt/datashield/backend/.env）
- 桌面打包：`cd desktop && npm run dist`（产物 desktop/release/DataShield Setup 0.1.0.exe；打包前必须 taskkill DataShield.exe；前端必须 `npm run build -- --base=./` 再进包）
- 管理后台：/admin，密钥 `DS-Admin-2026-ab17f3c9`
- 截图验证法：`powershell -ExecutionPolicy Bypass -File C:\Users\jiang\AppData\Local\Temp\shot.ps1`（聚焦 DataShield 窗口并截全屏到 Temp\ds_screen.png，用 ReadMediaFile 看）；浏览器页面级验证用 curl 取 200 + 源码走查
- 浏览器请求后端要带 `Origin: http://localhost:5173` 头

## 已知 BUG（优先修）
1. **整改草案详情页黑屏**：线上 /app/actions/5 点"打开草案，开始审阅"后整页黑屏。代码 `frontend/src/pages/new/ActionsExperience.tsx` 的 `ActionDetail`（第 5 行，单函数巨型 JSX）。高度怀疑：某 remediation 的 `d.plan` 或字段为 null（如 `p.issue`、`r.status.toLowerCase()`、`p.requested_changes.map`）导致 React 渲染抛异常，而**全站没有 ErrorBoundary**，任何渲染错误→黑屏。必修：
   - 用 demo 账户调 `GET /api/v1/remediations/5`（或对应 id）看真实返回结构，定位空字段
   - ActionDetail 全部字段防御性渲染（`?.`+兜底）
   - 在 App.tsx 或 AppShell 加全局 ErrorBoundary（出错显示"页面出错了，点我返回"双语，不黑屏）
   - 同类巨型 JSX 页面（FindingDetailPage 等）一并排查空字段风险
   - 修完 pytest + build + 真实复现路径验证

## 上一轮遗留（已完成大部分，复核）
- 工作台枚举中文化已全部做完（today/findings/monitor/onboarding，699 keys 对齐）；后端 today.py 两条英文标题已改中文
- **未做浏览器端实际渲染验证**（此前无头）：landing hero 字号、行动页生成→结果卡→详情审阅流、今日页空态指南卡——本次必须截图实测

## 全面设计验证清单（每个按钮都点）
1. **公开区**：/（hero 比例、三步、功能卡、双语切换）、/features（锚点滚动）、/plans、/choose、/login、/signup、/admin（密码门+四标签每操作一遍）
2. **认证流**：注册→onboarding（手动描述流跑到出 finding）→退出→登录→设置页退出
3. **工作台**：Today（指南卡、卡片点击）/ Monitor / Findings 列表+详情（生成整改草案按钮）/ Actions 列表+**详情（黑屏修复后复核）**+采纳/拒绝按钮+复制按钮 / Product（事实纠正展开）/ Regulations（搜索、展开、双语）/ Settings
4. **演示模式**：一键演示→各页
5. **双语**：以上每类页面 中/EN 各过一遍，残留英文即修
6. **桌面版**：安装包安装→双击→注册→Today 加载→关闭→后端退出→重开→数据保留；外部 curl 无 token 401
7. **线上**：http://123.57.252.25 主路径全过一遍（部署最新代码后）
8. pytest 300 全绿 + 前端 build 通过是硬门槛

## 视觉/体验打磨标准（"赏心悦目"）
- 中文优先、无英文残留；无黑屏/裸报错；空态都有引导；按钮有 hover/反馈；Landing 比例协调
- 发现粗糙处直接改（ds-* 体系内），不攒问题

## 最终交付物
1. 代码全部 commit（分阶段 message）
2. 云端更新 + 线上验证通过
3. 重打安装包并验收
4. **产品说明书**：`D:\DataShield\docs\产品说明书.md`——产品定位与目标用户、核心功能逐一说明（配图位/操作路径）、三大版本对比、技术架构简述、安装与使用指南（网页版+桌面版+管理后台）、隐私与免责声明。写好后连同 commit 一起交付，并向用户汇报：验证结果总表、修复清单、说明书路径、线上地址、安装包路径、管理员密钥。


---

# 10-07 深夜补充（用户追加，同为凌晨任务）

## A. 语言底座推倒重来（最高优先级，用户原话"极度恶心、推倒重来"）
参照问题截图 /app/findings/7：标题 "Ai disclosure may be insufficient"（英文）、正文"产品事实满足该 Requirement 的确定性适用条件"（中英混杂）、NOT_DETECTED 原文、"Product Twin 状态"、"Provide clear AI interaction transparency information"（英文法规要求无翻译）、"责任主体: Provider"、"目标市场: EU,US,UK"。用户要求**所有语言基于中国人的语言习惯和思维重写**，不是打补丁式映射：

1. **后端生成内容中文化**（根源治理）：
   - demo 种子 requirement（backend/app/api/evaluation.py `_demo_requirement`："EU AI Transparency Demo Requirement"、"Provide clear AI interaction transparency information"）改为中文名称与中文概述（如"欧盟 AI 法案·透明度义务"/"向用户明确告知其正在与 AI 系统交互"）
   - MockLLM/确定性生成器（finding 标题、gap_summary、applicability 说明等，搜 backend/app 下生成英文标题的模板）改中文模板
   - 真实 LLM（DeepSeek）的 prompts 明确要求**中文输出**（remediation planner、feedback planner、tenant agent 各节点）
   - 注意库中已有英文脏数据：在 admin reseed 或迁移中清洗，或在展示层兼容旧数据
2. **前端展示层**：
   - 杜绝 Requirement/Product Twin/NOT_DETECTED 等原文混入中文句子（要么映射，要么重构句式：如"该法规条款的适用条件已满足，且未命中例外"）
   - "责任主体: Provider"→"责任主体：服务提供方"；"目标市场: EU,US,UK"→"目标市场：欧盟、美国、英国"
3. **法规与实际关联"不伦不类"**：finding→法规条款→证据 的链路重新设计展示——"依据哪部法规哪一条（中文概述）+ 触发条件 + 你的现状 + 差距"四段式；英文法规原文（GDPR 条文）作为"原文对照"折叠展示，默认中文

## B. 按键问题（用户："按键问题非常大，特别在行动里"）
- 行动页所有按钮逐一实测：起草文档草案/改起草代码说明/打开草案/采纳/拒绝/复制说明——可点、有 loading、有结果反馈、不黑屏（连同黑屏 BUG 一起修）
- 全站按钮普查：凡无 hover、无点击反馈、点了没反应的即修

## C. 管理后台升级：新增 System 区（第五个标签页）
- Global RegIntel/法规库管理（现有法规表格移入并可扩：来源 sources 列表、手动触发 ingest `POST /v1/sources/{id}/ingest`）
- 用户/Workspace 基础管理（现有两表移入）
- Demo Workspace/Demo 数据重置（现有）
- **RegIntel sync 状态**：sources 轮询状态、最近 ingestion-runs（`GET /v1/ingestion-runs`）、events、scheduler 开关状态（SCHEDULER_ENABLED）
- **后端信息**：版本、DB 类型、LLM provider/模型、embedding provider、健康状态、环境（由 admin API 新增 GET /v1/admin/system 返回）
- admin API 补齐对应端点 + 测试

## D. Admin 登录页对比度 BUG
/admin 密码门的"管理员验证"标题几乎看不见（浅色字撞浅色底——读 public.css 的 ds-admin 段修对比度，检查整页文字可见性）

## E. Logo 使用（文件已备好：frontend/public/logo.png，1254x1254 盾牌）
- Landing 顶栏品牌区、登录/注册页、工作台侧边栏、admin 密码门 用真 logo 替换现在的"D"方块
- favicon：index.html 加 <link rel="icon" href="/logo.png">
- 桌面版：electron-builder 配置 win.icon 用该图（需转 .ico，可用在线工具或 png 直接配 build/icon.png，electron-builder 支持 png）
- 启动画面/关于区可选

## F. 灵魂一问的设计方向（用户允许较大幅度改动）
"作为用户希望什么软件、怎么操作"——按此重新审视信息架构：
- 核心主张：打开软件 → 说一句话描述产品 → 10 分钟内拿到"哪里违规+怎么改"。一切页面围绕这条主线
- 可考虑：注册后直奔"描述产品"（onboarding 已是），工作台首页 Today 强化主线引导；"合规发现"是主线列表，"整改行动"是结果列表，法规库/监测是辅助
- Landing 第一屏就让访客看懂并能点开始检查
- 允许重排导航、合并页面、改首页，但保持后端契约不动、测试全绿

## 交付物追加
- 产品说明书中包含 logo 与品牌呈现
- 汇报时说明：语言底座改造覆盖的后端模板清单、System 区端点清单、按钮普查结果
