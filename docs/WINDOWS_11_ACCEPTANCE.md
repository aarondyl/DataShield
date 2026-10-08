# Windows 11 实机验收表

必须记录安装器 SHA256、`SOURCE_COMMIT.txt`、Windows build、普通用户/管理员状态、时间和执行者。自动化 CI 安装目录测试、真实 Windows 自动化和用户人工操作分别报告，不互相冒充。

| 步骤 | 操作 | 通过标准 |
| --- | --- | --- |
| 1 | 普通用户核对 SHA256，安装并启动 | 当前用户安装成功，窗口和 Local Runtime 就绪，无需 Python/Node |
| 2 | 查看默认中文，切换 English，退出重启 | 两种语言所有业务可操作，偏好保存 |
| 3 | 启动时查看进程及 loopback 监听，退出后再检查 | 动态非零端口，仅 127.0.0.1，sidecar 为本次子进程；正常退出无遗留 sidecar 和描述文件 |
| 4 | 重启两次，不复制 token 到截图/日志 | Runtime Token 每次不同，缺失/旧 token 请求私有接口得到 401 |
| 5 | 创建工作区、手动事实、网站/授权仓库理解并确认 | SQLite 数据存在；新 Twin 版本和事实审核历史可查 |
| 6 | 连接经过验收的实际 HTTPS Cloud，同步 | 使用可信证书，无 operator key；法规、版本、义务及 cursor 写入 SQLite |
| 7 | 断开网络、读取缓存、再次同步；恢复网络再同步 | 原缓存可读，明确离线错误，网络恢复后继续；不清空业务数据 |
| 8 | 运行 Agent 并查看 Finding/Evidence | 来源为已审核官方法规，有正文、版本、摘要状态和真实 Twin/run 引用；模拟模型明确标识 |
| 9 | 创建两个整改，分别批准和拒绝 | 状态及历史正确，批准没有执行代码或自动宣称已解决 |
| 10 | 反馈、澄清、确认、应用、更正、重新分析 | 确认与应用分离；新 Twin 和关联 run 保留，Today 随真实结果变化 |
| 11 | 重启 Desktop 和 Windows | SQLite 工作区、法规缓存和历史仍在；Runtime Token 重新生成 |
| 12 | 退出后备份数据、卸载、重新安装和升级候选 | 逐项记录实际保留/丢失行为；升级前后业务记录及 schema 正确 |

人工验收需要回传：每项 PASS/FAIL/未执行、截图（不含 token/私有业务文件）、失败最小复现、Windows build、安装器 SHA256。不要只回传“能打开”。真实 HTTPS 未就绪时，第 6–10 步不能用临时 HTTP 或演示语料替代。

完整重启、真实业务操作和升级后的用户数据观察必须实际执行；无法远程操作时由用户完成并反馈。若发现 P0，修复后从新固定提交重新构建并重复受影响步骤，再申请最终发布批准。

本轮旧 RC 的 Windows 自动化已有记录于 `docs/integration-evidence/windows-installed-79d1c513.json`，但该包已被修复取代，不能作为新 RC 的全项 PASS。网站理解还须在正常公网 DNS 下复验；当前 fake-IP 解析被安全拒绝。

新版 `6dbd53b2` 已实际安装并自动化复验冷启动自动连接、英文导航/偏好、GUI Twin 时间、SQLite 持久化、正常退出、token 轮换和模拟业务 API 闭环。独立 RC 的卸载保留 SQLite（文件 SHA256 不变），同包重装工作区仍在；这不是跨版本升级、用户人工或实际 HTTPS 验收。新包位于 `C:\Users\Aaron\Downloads\DataShield-RC-6dbd53b2`。
