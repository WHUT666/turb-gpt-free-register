# -*- coding: utf-8 -*-
"""Generate dist sidecar files with correct UTF-8 encoding (Windows-safe)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
DIST.mkdir(parents=True, exist_ok=True)

ENV_TEXT = """# turb-gpt-register.exe 同目录配置（改完保存即可）
USE_EMAIL_SERVICE=True
EMAIL_SOURCE=yahoos
REGISTER_EMAIL=
REGISTRATION_DRIVER=protocol
ENABLE_CODEX_AUTO=False
ENABLE_CODEX_AGENT_IDENTITY=True
SSL_VERIFY=False
# 代理池：一行一个；本地 Clash 示例
PROXY_POOL=socks5://127.0.0.1:7897
"""

README_TEXT = """turb-gpt-register.exe 使用说明
================================

1. 本机需已安装 Node.js（注册 Sentinel 步骤需要 node）
2. 编辑同目录 .env：
   - PROXY_POOL=socks5://127.0.0.1:7897
   - EMAIL_SOURCE=yahoos（默认，faker 英文名+4位数字）
   - SSL_VERIFY=False（Clash 等 MITM 代理建议关闭校验）
3. 运行：
   turb-gpt-register.exe -n 1 --verbose
   turb-gpt-register.exe -n 3 --continue-on-fail

输出目录（与 exe 同级）：
  accounts\\
  codex_accounts\\codex-agent-*.json
  注册成功的邮箱.json
"""


def main() -> None:
    (DIST / ".env.example").write_text(ENV_TEXT, encoding="utf-8", newline="\n")
    env_path = DIST / ".env"
    if not env_path.exists():
        env_path.write_text(ENV_TEXT, encoding="utf-8", newline="\n")

    # 只用 ASCII 文件名，避免部分 IDE/资源管理器把 UTF-8 中文文件名显示成乱码
    (DIST / "README.txt").write_text(README_TEXT, encoding="utf-8-sig", newline="\r\n")

    for p in DIST.glob("*.txt"):
        if p.name in {"README.txt", "smoke_out.txt", "smoke_err.txt"}:
            continue
        if p.name == "使用说明.txt" or "浣" in p.name or "璇" in p.name:
            try:
                p.unlink()
            except OSError:
                pass

    print("ok", DIST)
    print("readme", (DIST / "README.txt").resolve())


if __name__ == "__main__":
    main()
