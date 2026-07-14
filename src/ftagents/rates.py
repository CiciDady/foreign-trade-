"""实时汇率(人民币兑美元),带缓存与降级。

设计与 ``llm.py`` 一致:只用标准库(urllib),网络不可用时优雅降级到默认值,
绝不因为取汇率失败而中断主流程。

数据源(免费、无需 key,按顺序尝试):
1. https://open.er-api.com/v6/latest/USD
2. https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json
"""

from __future__ import annotations

import json
import time
import urllib.request

DEFAULT_CNY_PER_USD = 7.2
_CACHE_TTL = 3600.0  # 1 小时

_PROVIDERS = (
    ("open.er-api.com", "https://open.er-api.com/v6/latest/USD",
     lambda d: d.get("rates", {}).get("CNY")),
    ("fawazahmed0", "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
     lambda d: d.get("usd", {}).get("cny")),
)

_cache: dict[str, float | str | None] = {"rate": None, "source": None, "ts": 0.0}


def _fetch(url: str, timeout: float) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "ftagents/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_live(timeout: float) -> tuple[float, str] | None:
    for name, url, extract in _PROVIDERS:
        try:
            rate = extract(_fetch(url, timeout))
            if rate and float(rate) > 0:
                return round(float(rate), 4), name
        except Exception:  # noqa: BLE001 - 任意失败都继续尝试下一个/降级
            continue
    return None


def get_cny_per_usd(*, timeout: float = 8.0, use_cache: bool = True) -> tuple[float, str]:
    """返回 (汇率, 来源)。来源为 provider 名或 ``"fallback"``(降级到默认值)。"""

    now = time.time()
    if use_cache and _cache["rate"] and (now - float(_cache["ts"])) < _CACHE_TTL:
        return float(_cache["rate"]), str(_cache["source"])

    live = _fetch_live(timeout)
    if live is None:
        return DEFAULT_CNY_PER_USD, "fallback"

    rate, source = live
    _cache.update(rate=rate, source=source, ts=now)
    return rate, source
