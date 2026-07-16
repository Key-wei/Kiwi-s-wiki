import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build_docs


def test_convert_image_embed():
    assert build_docs.convert_embeds("![[mermaid-diagram.png]]") == "![](mermaid-diagram.png)"


def test_convert_image_embed_with_alias():
    assert build_docs.convert_embeds("![[a.png|320]]") == "![](a.png)"


def test_convert_leaves_wikilink_untouched():
    assert build_docs.convert_embeds("见 [[工厂方法模式]]") == "见 [[工厂方法模式]]"


def test_build_creates_partitions(tmp_path):
    for d, f in (("40_知识库", "a.md"), ("30_研究", "b.md"), ("20_项目", "c.md")):
        (tmp_path / d).mkdir()
        (tmp_path / d / f).write_text("# t", encoding="utf-8")
    (tmp_path / "40_知识库" / "attachments").mkdir()
    (tmp_path / "40_知识库" / "attachments" / "p.png").write_bytes(b"x")
    (tmp_path / "40_知识库" / "embed.md").write_text("![[p.png]]", encoding="utf-8")
    assets = tmp_path / "site_src"; assets.mkdir()
    (assets / "index.md").write_text("home", encoding="utf-8")
    out = tmp_path / "site_docs"
    build_docs.build(tmp_path, out, assets)
    assert (out / "知识库" / "a.md").exists()
    assert (out / "研究" / "b.md").exists()
    assert (out / "项目" / "c.md").exists()
    assert (out / "知识库" / "attachments" / "p.png").exists()
    assert (out / "index.md").exists()
    assert (out / "知识库" / "embed.md").read_text(encoding="utf-8") == "![](p.png)"
