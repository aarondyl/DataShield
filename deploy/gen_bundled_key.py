"""构建期生成混淆的内置 LLM key 模块（输出文件已被 .gitignore，不入库）。
用法: DS_KEY=sk-xxx python deploy/gen_bundled_key.py
"""
import base64
import os
import secrets

KEY = os.environ["DS_KEY"]
OUT = os.path.join(os.path.dirname(__file__), "..", "backend", "app", "core", "bundled_key.py")

mask = secrets.token_bytes(24)
blob = bytes(b ^ mask[i % len(mask)] for i, b in enumerate(KEY.encode()))

content = '''"""内置 LLM 凭证（构建期由 deploy/gen_bundled_key.py 生成，混淆存储，勿编辑勿入库）。

注意：这只是防随手翻看的混淆，不是真正的加密——任何打进客户端的密钥
都无法抵御有意的逆向。需要更强保护时应改用服务端中转。
"""
import base64 as _b64

_B = {blob!r}
_M = {mask!r}


def get_bundled_llm_key() -> str:
    data = _b64.b64decode(_B)
    mask = _b64.b64decode(_M)
    return bytes(b ^ mask[i % len(mask)] for i, b in enumerate(data)).decode()
'''.format(blob=base64.b64encode(blob), mask=base64.b64encode(mask))

with open(OUT, "w", encoding="utf-8") as f:
    f.write(content)
print(f"written {os.path.abspath(OUT)}")
