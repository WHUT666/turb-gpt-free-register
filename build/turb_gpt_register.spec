# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：CLI 注册工具 turb-gpt-register.exe"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
root = Path(SPECPATH).resolve().parent

datas = [
    (str(root / "sentinel"), "sentinel"),
    (str(root / "config"), "config"),
]

binaries = []
hiddenimports = [
    "curl_cffi",
    "curl_cffi.requests",
    "faker",
    "cryptography",
    "cryptography.hazmat.primitives.asymmetric.ed25519",
    "pyotp",
    "requests",
    "dotenv",
    "codex_agent",
    "nacl",
    "nacl.public",
    "core.yahoos_client",
    "core.outlook_tw_client",
    "core.email_provider",
    "core.session",
    "core.openai_auth",
    "core.sentinel_runner",
    "core.account_export",
    "core.db",
    "config.runtime_paths",
    "config.env_loader",
    "config.email",
    "config.proxy",
    "config.codex",
]

# curl_cffi / faker 常需整包收集
for pkg in ("curl_cffi", "faker", "certifi"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception:
        pass

try:
    hiddenimports += collect_submodules("core")
    hiddenimports += collect_submodules("config")
except Exception:
    pass

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "webui",
        "flask",
        "playwright",
        "selenium",
        "cloakbrowser",
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="turb-gpt-register",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
