"""报告输出工具。

skill 脚本产出结构化 JSON 供 agent 推理；同时可落地一份人类可读的 Markdown
报告作为存档。这里提供最小的 Markdown 拼装工具，不依赖模板引擎。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

DISCLAIMER = (
    "> **免责声明**：本报告由 lab_bot 自动生成，仅用于量化研究与决策支持，"
    "不构成任何投资建议。市场有风险，决策与风险由使用者自行承担。"
)


def df_to_md(df: pd.DataFrame, max_rows: int = 30) -> str:
    """把 DataFrame 渲染为 Markdown 表格（无 tabulate 依赖）。"""
    if df is None or df.empty:
        return "_（无数据）_"
    df = df.head(max_rows)
    cols = list(df.columns)
    head = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = [
        "| " + " | ".join(str(v) for v in row) + " |"
        for row in df.itertuples(index=False, name=None)
    ]
    return "\n".join([head, sep, *body])


def write_report(
    title: str, sections: list[tuple[str, str]], output_dir: str | Path,
    *, fmt: str = "markdown", filename: str | None = None,
) -> Path:
    """写出报告文件。sections = [(小标题, markdown正文), ...]。返回文件路径。"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = filename or f"report_{ts}.md"
    path = out / name

    lines = [f"# {title}", "", f"_生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}_", "", DISCLAIMER, ""]
    for sub, body in sections:
        lines += [f"## {sub}", "", body, ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
