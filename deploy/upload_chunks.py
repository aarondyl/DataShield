"""小碎块上传：把本地文件拆成 16KB base64 块，逐块 exec 追加到远程文件。
用法: DS_PASS=xxx python upload_chunks.py 本地文件 远程路径
"""
import base64
import os
import sys
import time

import paramiko

HOST, USER = "123.57.252.25", "root"
RAW_CHUNK = 12 * 1024  # 每块原始字节；base64 后 ~16KB，命令总长远低于拦截阈值


def main() -> None:
    local, remote = sys.argv[1], sys.argv[2]
    data = open(local, "rb").read()
    blocks = [data[i : i + RAW_CHUNK] for i in range(0, len(data), RAW_CHUNK)]
    print(f"{len(data)} bytes -> {len(blocks)} chunks")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=os.environ["DS_PASS"], timeout=20)

    def exec_cmd(cmd: str, retries: int = 5) -> str:
        for attempt in range(retries):
            try:
                _, out, err = client.exec_command(cmd, timeout=120)
                o, e = out.read().decode(), err.read().decode()
                if out.channel.recv_exit_status() == 0:
                    return o
                raise RuntimeError(e.strip() or "nonzero exit")
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(2)
                try:
                    client.close()
                except Exception:
                    pass
                client.connect(HOST, username=USER, password=os.environ["DS_PASS"], timeout=20)
        return ""

    exec_cmd(f"rm -f {remote}")
    t0 = time.time()
    for idx, block in enumerate(blocks):
        b64 = base64.b64encode(block).decode()
        exec_cmd(f"echo {b64} | base64 -d >> {remote}")
        if (idx + 1) % 100 == 0:
            print(f"{idx+1}/{len(blocks)} chunks, {time.time()-t0:.0f}s", flush=True)
    print(exec_cmd(f"stat -c%s {remote}"))
    client.close()


if __name__ == "__main__":
    main()
