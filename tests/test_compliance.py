from ftagents.agents import ComplianceAgent
from ftagents.models import ComplianceStatus, MarketContext, ProductCandidate


def _product(**overrides):
    base = dict(
        id="T-1",
        name="test",
        category="yoga mat",
        supplier_cost_cny=72.0,
        weight_kg=1.0,
        est_monthly_sales=100,
        target_price_usd=50.0,
        competition_score=0.5,
    )
    base.update(overrides)
    return ProductCandidate(**base)


def test_green_for_low_risk_us():
    ctx = MarketContext(category="yoga mat", market="US")
    r = ComplianceAgent().run(_product(category="yoga mat"), ctx)
    assert r.status == ComplianceStatus.GREEN
    assert not r.blocking


def test_yellow_for_certification_required():
    ctx = MarketContext(category="bluetooth earbuds", market="US")
    p = _product(category="bluetooth earbuds", hazmat=["battery"])
    r = ComplianceAgent().run(p, ctx)
    assert r.status == ComplianceStatus.YELLOW
    assert "FCC" in r.required_certifications
    assert any("UN38.3" in t for t in r.todos)


def test_red_and_blocking_for_brand_risk():
    ctx = MarketContext(category="kids building blocks", market="US")
    p = _product(category="kids building blocks", brand_risk=True)
    r = ComplianceAgent().run(p, ctx)
    assert r.status == ComplianceStatus.RED
    assert r.blocking is True
    assert r.ip_risk is True


def test_restricted_category_flagged():
    ctx = MarketContext(category="kitchen knife set", market="US")
    p = _product(category="kitchen knife set", hazmat=["sharp"])
    r = ComplianceAgent().run(p, ctx)
    assert r.status == ComplianceStatus.YELLOW
    assert r.restrictions


def test_tax_obligations_present():
    ctx = MarketContext(category="yoga mat", market="EU")
    r = ComplianceAgent().run(_product(category="yoga mat"), ctx)
    assert any("VAT" in t for t in r.tax_obligations)
