import ftagents.rates as rates


def _reset_cache():
    rates._cache.update(rate=None, source=None, ts=0.0)


def test_live_success_primary(monkeypatch):
    _reset_cache()
    monkeypatch.setattr(rates, "_fetch", lambda url, timeout: {"rates": {"CNY": 6.95}})
    rate, source = rates.get_cny_per_usd(use_cache=False)
    assert rate == 6.95
    assert source == "open.er-api.com"


def test_falls_back_to_second_provider(monkeypatch):
    _reset_cache()

    def fetch(url, timeout):
        if "er-api" in url:
            raise OSError("primary down")
        return {"usd": {"cny": 6.8}}

    monkeypatch.setattr(rates, "_fetch", fetch)
    rate, source = rates.get_cny_per_usd(use_cache=False)
    assert rate == 6.8
    assert source == "fawazahmed0"


def test_fallback_default_when_all_fail(monkeypatch):
    _reset_cache()

    def boom(url, timeout):
        raise OSError("no network")

    monkeypatch.setattr(rates, "_fetch", boom)
    rate, source = rates.get_cny_per_usd(use_cache=False)
    assert rate == rates.DEFAULT_CNY_PER_USD
    assert source == "fallback"


def test_cache_reused(monkeypatch):
    _reset_cache()
    calls = {"n": 0}

    def fetch(url, timeout):
        calls["n"] += 1
        return {"rates": {"CNY": 7.01}}

    monkeypatch.setattr(rates, "_fetch", fetch)
    r1, _ = rates.get_cny_per_usd()
    r2, _ = rates.get_cny_per_usd()  # should hit cache, no extra fetch
    assert r1 == r2 == 7.01
    assert calls["n"] == 1
