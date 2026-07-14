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
