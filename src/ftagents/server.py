"""轻量 Web 服务(Python 标准库,无第三方依赖)。

提供:
- ``GET  /``                首页(单页 UI)
- ``GET  /api/categories``  可用示例品类
- ``GET  /api/health``      健康检查
- ``POST /api/analyze``     运行选品→合规→利润测算闭环,返回 JSON 结果

设计上复用 ``orchestrator.run_pipeline``,与 CLI 共享同一套确定性逻辑。
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .datastore import load_products
from .llm import LLMClient
from .models import MarketContext, ProductCandidate
from .orchestrator import NoCandidatesError, analyze_product, run_pipeline

_STATIC = Path(__file__).parent / "static"


def list_categories() -> list[str]:
    return sorted({p.category for p in load_products()})


def _context(payload: dict, category: str) -> MarketContext:
    return MarketContext(
        category=category,
        market=str(payload.get("market", "US")).strip() or "US",
        budget_usd=float(payload.get("budget") or 5000),
        cny_per_usd=float(payload.get("cny_per_usd") or 7.2),
    )


def _build_manual_product(spec: dict, category: str) -> ProductCandidate:
    return ProductCandidate(
        id="MANUAL",
        name=str(spec.get("name") or category or "自定义商品"),
        category=category,
        supplier_cost_cny=float(spec.get("supplier_cost_cny") or 0),
        weight_kg=float(spec.get("weight_kg") or 0),
        est_monthly_sales=int(float(spec.get("est_monthly_sales") or 0)),
        target_price_usd=float(spec.get("target_price_usd") or 0),
        competition_score=float(spec.get("competition_score") if spec.get("competition_score") is not None else 0.5),
        hazmat=list(spec.get("hazmat") or []),
        brand_risk=bool(spec.get("brand_risk", False)),
        markets=[],
    )


def analyze(payload: dict) -> dict:
    use_llm = bool(payload.get("use_llm", False))
    manual = payload.get("product")
    if manual:
        category = str(payload.get("category", "")).strip()
        product = _build_manual_product(manual, category)
        ctx = _context(payload, category)
        return analyze_product(ctx, product, use_llm=use_llm).to_dict()

    ctx = _context(payload, str(payload.get("category", "")).strip())
    return run_pipeline(ctx, use_llm=use_llm).to_dict()


def compare(payload: dict) -> dict:
    """批量对比多个品类,返回按机会分排序的紧凑结果数组。

    批量默认不走 LLM(慢且耗 token),单个展开时再按需增强。
    """

    categories = payload.get("categories") or []
    use_llm = bool(payload.get("use_llm", False))
    rows: list[dict] = []
    for cat in categories:
        cat = str(cat).strip()
        if not cat:
            continue
        ctx = _context(payload, cat)
        try:
            result = run_pipeline(ctx, use_llm=use_llm)
        except NoCandidatesError:
            rows.append({"category": cat, "error": "无匹配候选"})
            continue
        p = result.scored_candidate
        rows.append(
            {
                "category": cat,
                "product": p.product.name,
                "market": ctx.normalized_market(),
                "verdict": result.recommendation.verdict.value,
                "opportunity_score": p.opportunity_score,
                "margin_pct": result.profit.margin_pct,
                "unit_profit": result.profit.unit_profit,
                "monthly_profit": result.profit.monthly_profit,
                "roi_pct": result.profit.roi_pct,
                "compliance": result.compliance.status.value,
                "blocking": result.compliance.blocking,
            }
        )

    def _sort_key(r: dict):
        return (0 if "error" in r else 1, r.get("opportunity_score", 0))

    rows.sort(key=_sort_key, reverse=True)
    return {"rows": rows}


def llm_status() -> dict:
    client = LLMClient()
    return {"available": client.available, "model": client.model if client.available else None}


class Handler(BaseHTTPRequestHandler):
    server_version = "ftagents/0.1"

    def _send(self, code: int, body, ctype: str = "application/json; charset=utf-8") -> None:
        data = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            try:
                html = (_STATIC / "index.html").read_bytes()
            except OSError:
                self._send(500, "index.html not found")
                return
            self._send(200, html, "text/html; charset=utf-8")
            return
        if self.path == "/api/categories":
            self._json(200, {"categories": list_categories(), "llm": llm_status()})
            return
        if self.path == "/api/health":
            self._json(200, {"ok": True})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in ("/api/analyze", "/api/compare"):
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, TypeError):
            self._json(400, {"error": "请求体不是合法 JSON"})
            return

        try:
            if self.path == "/api/compare":
                if not payload.get("categories"):
                    self._json(400, {"error": "请至少选择一个品类"})
                    return
                self._json(200, compare(payload))
                return

            # /api/analyze
            if not str(payload.get("category", "")).strip():
                self._json(400, {"error": "请填写品类 (category)"})
                return
            self._json(200, analyze(payload))
        except NoCandidatesError as exc:
            self._json(404, {"error": str(exc)})
        except (ValueError, TypeError) as exc:
            self._json(400, {"error": f"参数错误: {exc}"})
        except Exception as exc:  # pragma: no cover - defensive
            self._json(500, {"error": f"内部错误: {exc}"})

    def log_message(self, *args) -> None:  # 静默默认访问日志
        return


def make_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ftagents-web", description="外贸选品闭环 Web UI")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址,默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="端口,默认 8000")
    args = parser.parse_args(argv)

    httpd = make_server(args.host, args.port)
    print(f"ftagents web 运行于 http://{args.host}:{args.port}  (Ctrl+C 退出)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
