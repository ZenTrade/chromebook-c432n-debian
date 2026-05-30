#!/usr/bin/env python3
"""
r.py — SSH 远程命令执行工具
===========================

用法：
    python r.py "uname -r"
    python r.py "aplay -l"

功能：通过 paramiko SSH 连接 Chromebook，执行单条命令并打印输出。

连接参数（需自行配置）：
    主机: <CHROMEBOOK_IP>
    用户: root
    密码: <CHROMEBOOK_ROOT_PASSWORD>
    超时: 120 秒

如需修改连接参数，编辑下方 run() 函数的默认值。
"""

import paramiko
import sys

def run(cmd, user='root', password='<CHROMEBOOK_ROOT_PASSWORD>', timeout=120):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect('<CHROMEBOOK_IP>', username=user, password=password, timeout=timeout)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    client.close()
    if out:
        print(out, end='')
    if err:
        print(err, end='', file=sys.stderr)
    return code

if __name__ == '__main__':
    cmd = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else 'echo hello'
    sys.exit(run(cmd))
