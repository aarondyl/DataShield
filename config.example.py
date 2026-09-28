# -*- coding: utf-8 -*-
"""数盾 DataShield 配置示例。

复制本文件为 config.py 后填写真实值即可（config.py 已被 .gitignore 忽略）。
优先级：环境变量 > Streamlit secrets > config.py > 内置默认值。
"""

# DeepSeek API Key。到 https://platform.deepseek.com/ 控制台创建。
# 留空（""）则不启用 AI，应用自动使用纯规则模式，功能完整可用。
API_KEY = ""

# OpenAI 兼容接口地址（一般用默认值即可）
BASE_URL = "https://api.deepseek.com/v1"

# 模型名称。若调用时报"模型不存在"，改为平台文档中的实际模型名，如 deepseek-chat
MODEL = "deepseek-v4.1-flash"

# 请求超时时间（秒），超时后自动降级
TIMEOUT = 20

# 生成参数：温度越低回答越稳定；max_tokens 限制回复长度
TEMPERATURE = 0.3
MAX_TOKENS = 600
