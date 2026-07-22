# -*- coding: utf-8 -*-
import re
from pathlib import Path

html = Path(r"C:\Users\Quentin\AppData\Local\Temp\msal_simple.html").read_text(
    encoding="utf-8", errors="ignore"
)
links = re.findall(
    r'href="(\.\./\.\./packages/[^"]+/(msal-([0-9][^"#]+)-py2\.py3-none-any\.whl))',
    html,
)
stable = [x for x in links if "a" not in x[2] and "b" not in x[2] and "rc" not in x[2]]


def ver_key(item):
    return [int(p) for p in re.split(r"[^0-9]+", item[2]) if p.isdigit()]


stable = sorted(stable, key=ver_key)
rel, name, ver = stable[-1]
url = "https://pypi.tuna.tsinghua.edu.cn/packages/" + rel.split("/packages/")[-1]
print(name, ver)
print(url)
Path(r"C:\Users\Quentin\AppData\Local\Temp\msal_wheel_url.txt").write_text(url, encoding="utf-8")
