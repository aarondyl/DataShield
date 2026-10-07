"""分块 stdin 上传：python upload_stdin.py 本地文件 远程路径（DS_PASS 提供密码）。"""
import base64
import os
import sys

import paramiko

HOST, USER = "123.57.252.25", "root"
CHUNK = 256 * 1024


def main() -> None:
    local, remote = sys.argv[1], sys.argv[2]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=os.environ["DS_PASS"], timeout=20)
    try:
        cmd = f"base64 -d > {remote} && echo UPLOAD_OK $(stat -c%s {remote})"
        stdin, stdout, stderr = client.exec_command(cmd, timeout=900)
        sent = 0
        with open(local, "rb") as f:
            while True:
                block = f.read(CHUNK)
                if not block:
                    break
                stdin.write(base64.b64encode(block))
                sent += len(block)
        stdin.channel.shutdown_write()
        out = stdout.read().decode()
        err = stderr.read().decode()
        print(f"sent {sent} bytes; remote says: {out.strip()} {err.strip()}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
