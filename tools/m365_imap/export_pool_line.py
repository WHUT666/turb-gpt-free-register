# -*- coding: utf-8 -*-
"""把 get_token.py 产出的 refresh_token 转成项目邮箱池一行。"""
from __future__ import annotations

import sys
from pathlib import Path

import config

CLIENT_ID = config.ClientId


def main() -> None:
    if len(sys.argv) < 3:
        print("用法: python export_pool_line.py <email> <password>")
        sys.exit(2)
    email = sys.argv[1].strip()
    password = sys.argv[2].strip()
    token_path = Path(config.RefreshTokenFileName)
    if not token_path.exists():
        print(f"缺少 {token_path}，请先运行: python get_token.py")
        sys.exit(1)
    refresh = token_path.read_text(encoding="utf-8").strip()
    if not refresh:
        print("refresh_token 为空")
        sys.exit(1)
    line = f"{email}----{password}----{CLIENT_ID}----{refresh}"
    print(line)
    out = Path("reauthed_one.txt")
    out.write_text(line + "\n", encoding="utf-8")
    print(f"已写入 {out.resolve()}")


if __name__ == "__main__":
    main()
