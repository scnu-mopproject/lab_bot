"""配置加载。

读取 config/config.yaml 并提供带默认值的访问。所有相对路径会被解析为
相对于项目根目录的绝对路径。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# 项目根目录 = 本文件上两级（lab_bot/config.py -> lab_bot/ -> 根）
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config" / "config.yaml"


@dataclass
class Config:
    """轻量配置封装，提供点号无关的嵌套访问。"""

    raw: dict[str, Any] = field(default_factory=dict)
    path: Path = DEFAULT_CONFIG_PATH

    def get(self, *keys: str, default: Any = None) -> Any:
        """按层级取值，如 cfg.get("data", "source")。任一层缺失返回 default。"""
        node: Any = self.raw
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def resolve_path(self, *keys: str, default: str | None = None) -> Path:
        """取配置中的路径并解析为绝对路径（相对路径基于项目根目录）。"""
        value = self.get(*keys, default=default)
        if value is None:
            raise KeyError(f"配置缺少路径项: {'/'.join(keys)}")
        p = Path(value)
        return p if p.is_absolute() else ROOT / p


def load_config(path: str | os.PathLike | None = None) -> Config:
    """加载配置文件，文件不存在时返回空配置（依赖各模块默认值）。"""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        return Config(raw={}, path=cfg_path)
    with open(cfg_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return Config(raw=raw, path=cfg_path)
