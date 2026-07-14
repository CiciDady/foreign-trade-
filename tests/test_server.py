import json
import threading
import urllib.error
import urllib.request

from ftagents.server import make_server


def _start():
    httpd = make_server("127.0.0.1", 0)  # ephemeral port
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, port


def _post(base, obj):
    req = urllib.request.Request(
        base + "/api/analyze",
        data=json.dumps(obj).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=10)


def test_index_and_categories():
    httpd, port = _start()
    try:
        base = f"http://127.0.0.1:{port}"
        html = urllib.request.urlopen(base + "/").read().decode("utf-8")
        assert "外贸选品决策" in html

        data = json.loads(urllib.request.urlopen(base + "/api/categories").read())
        assert "yoga mat" in data["categories"]
        assert "available" in data["llm"]
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_fx_endpoint_structure():
    httpd, port = _start()
    try:
        base = f"http://127.0.0.1:{port}"
        data = json.loads(urllib.request.urlopen(base + "/api/fx", timeout=15).read())
        assert data["cny_per_usd"] > 0
        assert isinstance(data["source"], str)
        assert "live" in data
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_analyze_endpoint():
    httpd, port = _start()
    try:
        base = f"http://127.0.0.1:{port}"
        res = _post(base, {"category": "yoga mat", "market": "US", "use_llm": False})
        payload = json.loads(res.read())
        assert payload["recommendation"]["verdict"] in {"GO", "CAUTION", "NO-GO"}
        assert payload["profit"]["margin_pct"] is not None
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_analyze_missing_category_returns_400():
    httpd, port = _start()
    try:
        base = f"http://127.0.0.1:{port}"
        try:
            _post(base, {"market": "US"})
            raise AssertionError("expected HTTP 400")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_analyze_unknown_category_returns_404():
    httpd, port = _start()
    try:
        base = f"http://127.0.0.1:{port}"
        try:
            _post(base, {"category": "no-such-category-xyz"})
            raise AssertionError("expected HTTP 404")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_manual_mode_uses_provided_product():
    httpd, port = _start()
    try:
        base = f"http://127.0.0.1:{port}"
        res = _post(
            base,
            {
                "category": "yoga mat",
                "market": "US",
                "use_llm": False,
                "product": {
                    "name": "自定义垫",
                    "supplier_cost_cny": 72,
                    "weight_kg": 1.0,
                    "target_price_usd": 50,
                    "est_monthly_sales": 300,
                    "competition_score": 0.4,
                    "hazmat": [],
                    "brand_risk": False,
                },
            },
        )
        payload = json.loads(res.read())
        assert payload["scored_candidate"]["product"]["name"] == "自定义垫"
        assert payload["scored_candidate"]["product"]["id"] == "MANUAL"
        assert payload["profit"]["unit_profit"] > 0
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_manual_mode_flags_brand_risk_blocking():
    httpd, port = _start()
    try:
        base = f"http://127.0.0.1:{port}"
        res = _post(
            base,
            {
                "category": "custom-gadget",
                "use_llm": False,
                "product": {
                    "name": "山寨玩具",
                    "supplier_cost_cny": 40,
                    "weight_kg": 0.5,
                    "target_price_usd": 30,
                    "est_monthly_sales": 200,
                    "competition_score": 0.5,
                    "brand_risk": True,
                },
            },
        )
        payload = json.loads(res.read())
        assert payload["compliance"]["blocking"] is True
        assert payload["recommendation"]["verdict"] == "NO-GO"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_compare_endpoint_returns_sorted_rows():
    httpd, port = _start()
    try:
        base = f"http://127.0.0.1:{port}"
        req = urllib.request.Request(
            base + "/api/compare",
            data=json.dumps(
                {"categories": ["yoga mat", "led strip light", "kids building blocks"], "use_llm": False}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        payload = json.loads(urllib.request.urlopen(req, timeout=10).read())
        rows = payload["rows"]
        assert len(rows) == 3
        scores = [r["opportunity_score"] for r in rows]
        assert scores == sorted(scores, reverse=True)
        kids = next(r for r in rows if r["category"] == "kids building blocks")
        assert kids["verdict"] == "NO-GO"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_compare_requires_categories():
    httpd, port = _start()
    try:
        base = f"http://127.0.0.1:{port}"
        req = urllib.request.Request(
            base + "/api/compare",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            raise AssertionError("expected HTTP 400")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        httpd.shutdown()
        httpd.server_close()
