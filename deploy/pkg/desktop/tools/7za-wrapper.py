"""7za 包装器：规避无管理员权限时 winCodeSign 缓存解压失败。

electron-builder 解压 winCodeSign-*.7z 时会尝试创建其中的 darwin 软链
（libcrypto.dylib / libssl.dylib），Windows 非管理员且无开发者模式会报
"客户端没有所需的特权" 导致整个打包失败。这两个文件仅用于 macOS 签名，
Windows 打包用不到，故对 winCodeSign 相关解压追加排除参数后转发给真正的
7za（同目录 7za-real.exe）。
"""

import os
import subprocess
import sys

real = os.path.join(os.path.dirname(sys.executable), "7za-real.exe")
args = sys.argv[1:]
if any("winCodeSign" in a for a in args):
    args += ["-xr!libcrypto.dylib", "-xr!libssl.dylib"]
sys.exit(subprocess.call([real, *args]))
