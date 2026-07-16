#!/usr/bin/env python3
"""把 vault 知识类目录同步到 MkDocs 内容源目录 site_docs/。vault 笔记只读。"""
import re
import shutil
from pathlib import Path

VAULT = Path(__file__).resolve().parent
OUT = VAULT / "site_docs"
ASSETS = VAULT / "site_src"

PARTITIONS = {"40_知识库": "知识库", "30_研究": "研究", "20_项目": "项目"}

_EMBED_IMG = re.compile(
    r"!\[\[([^\]|]+\.(?:png|jpe?g|gif|svg|webp))(?:\|[^\]]*)?\]\]", re.IGNORECASE
)


def convert_embeds(text: str) -> str:
    """Obsidian 图片嵌入 ![[x.png]] / ![[x.png|alt]] → 标准 ![](x.png)。普通双链不动。"""
    return _EMBED_IMG.sub(lambda m: f"![]({m.group(1)})", text)


def _clean(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)


def _copy_partition(src: Path, dst: Path) -> None:
    for p in src.rglob("*"):
        target = dst / p.relative_to(src)
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif p.suffix.lower() == ".md":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(convert_embeds(p.read_text(encoding="utf-8")), encoding="utf-8")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)


def _copy_assets(assets: Path, out: Path) -> None:
    for name in ("index.md", "stylesheets", "javascripts"):
        s = assets / name
        if s.is_dir():
            shutil.copytree(s, out / name, dirs_exist_ok=True)
        elif s.is_file():
            shutil.copy2(s, out / name)


def build(vault: Path = VAULT, out: Path = OUT, assets: Path = ASSETS) -> None:
    _clean(out)
    for src_name, part in PARTITIONS.items():
        src = vault / src_name
        if src.exists():
            _copy_partition(src, out / part)
    _copy_assets(assets, out)


if __name__ == "__main__":
    build()
    print(f"已构建 {OUT}")
