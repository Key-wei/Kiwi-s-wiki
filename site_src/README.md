# KIWI CODEX 本地知识库网站

私人、本地优先的知识库网站（MkDocs Material 暗色 + CODEX 游戏化 + 机械特效）。
内容来自 vault 的 `40_知识库 / 30_研究 / 20_项目`（只读同步，笔记零改动）。

## 运行
```bash
.venv/Scripts/python build_docs.py     # 同步内容到 site_docs/
.venv/Scripts/mkdocs serve             # 本地预览 http://localhost:8000
```

## 构建静态站（将来托管用）
```bash
.venv/Scripts/python build_docs.py && .venv/Scripts/mkdocs build   # 产物在 site/
```

## 改了什么
- 站点资源（样式/脚本/首页/模板）在 `site_src/`（纳入 git）
- `site_docs/`、`site/`、`.venv/` 为生成物，已 gitignore
