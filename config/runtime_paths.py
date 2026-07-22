# -*- coding: utf-8 -*-
"""运行时路径：兼容源码运行与 PyInstaller frozen exe。

- resource_root: 只读打包资源（sentinel/、内置文件）
- data_root: 可写数据与配置（.env、accounts/、codex_accounts/、日志）
  frozen 时为 exe 所在目录；源码时为项目根目录。
"""
from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def resource_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def data_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


# 兼容旧命名
def project_root() -> Path:
    """可写项目/数据根（等同 data_root）。"""
    return data_root()
