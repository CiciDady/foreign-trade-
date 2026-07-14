"""加载打包的示例数据(选品数据源、合规规则库、费率表)。

真实项目里这里会换成 Jungle Scout API / 自建爬虫 / 规则库检索;
原型阶段用本地 JSON 保证可离线跑通。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import ProductCandidate

_DATA_DIR = Path(__file__).parent / "data"


def _load_json(name: str) -> Any:
    with open(_DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_products() -> list[ProductCandidate]:
    raw = _load_json("products.json")
    return [ProductCandidate(**item) for item in raw]


@lru_cache(maxsize=1)
def load_compliance_rules() -> dict[str, Any]:
    return _load_json("compliance_rules.json")


@lru_cache(maxsize=1)
def load_fees() -> dict[str, Any]:
    return _load_json("fees.json")
