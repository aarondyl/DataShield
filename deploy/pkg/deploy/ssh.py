"""DataShield 服务器 SSH 助手：通过 paramiko 在远程执行命令/上传文件。
用法:
  DS_PASS=xxx python ssh.py exec "命令"
  DS_PASS=xxx python ssh.py upload 本地路径 远程路径
密码只从环境变量 DS_PASS 读取，不写入任何文件。
"""
import os
import sys
import time

import paramiko

HOST = "123.57.252.25"
USER = "root"
PASS = os.environ["DS_PASS"]


def connect() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=20, banner_timeout=30)
    return client


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> int:
    print(f"$ {cmd}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-3000:])
    if err and code != 0:
        print("STDERR:", err[-2000:], file=sys.stderr)
    print(f"[exit {code}]", flush=True)
    return code


def main() -> None:
    mode = sys.argv[1]
    client = connect()
    try:
        if mode == "exec":
            code = run(client, sys.argv[2], timeout=int(sys.argv[3]) if len(sys.argv) > 3 else 600)
            sys.exit(code)
        elif mode == "upload":
            local, remote = sys.argv[2], sys.argv[3]
            sftp = client.open_sftp()
            t0 = time.time()
            sftp.put(local, remote)
            print(f"uploaded {local} -> {remote} in {time.time()-t0:.1f}s")
            sftp.close()
        else:
            raise SystemExit(f"unknown mode {mode}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
