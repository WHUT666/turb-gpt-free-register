# -*- coding: utf-8 -*-
import re
import subprocess
import sys
from pathlib import Path
from urllib.request import urlretrieve

SIMPLE = "https://pypi.tuna.tsinghua.edu.cn/simple/{pkg}/"
BASE = "https://pypi.tuna.tsinghua.edu.cn/packages/"


def latest_wheel(pkg: str, pattern: str) -> tuple[str, str]:
    html_path = Path(f"{Path.home()}/AppData/Local/Temp/{pkg}_simple.html")
    subprocess.check_call(["curl.exe", "-sL", SIMPLE.format(pkg=pkg), "-o", str(html_path)])
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    links = re.findall(rf'href="(\.\./\.\./packages/[^"]+/({pattern}))"', html)
    stable = []
    for rel, name in links:
        ver = name.split("-")[1]
        if any(x in ver for x in ("a", "b", "rc")):
            continue
        nums = [int(p) for p in re.split(r"[^0-9]+", ver) if p.isdigit()]
        stable.append((nums, rel, name))
    if not stable:
        raise RuntimeError(f"no wheel for {pkg}")
    stable.sort(key=lambda x: x[0])
    _, rel, name = stable[-1]
    return name, BASE + rel.split("/packages/")[-1]


def install_wheel(pkg: str, pattern: str) -> None:
    name, url = latest_wheel(pkg, pattern)
    whl = Path(f"{Path.home()}/AppData/Local/Temp/{name}")
    print(f"download {name}")
    print(url)
    subprocess.check_call(["curl.exe", "-L", url, "-o", str(whl)])
    subprocess.check_call([sys.executable, "-m", "pip", "install", str(whl), "--no-deps"])


if __name__ == "__main__":
    install_wheel("pyjwt", r"PyJWT-[0-9][^#\"]+-py3-none-any\.whl")
    import jwt
    import msal

    print("ok msal", msal.__version__, "PyJWT", jwt.__version__)
