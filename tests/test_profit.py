from ftagents.agents import ProfitAgent
from ftagents.models import MarketContext, ProductCandidate


def _product(**overrides):
    base = dict(
        id="T-1",
        name="test",
        category="yoga mat",
        supplier_cost_cny=72.0,  # /7.2 = $10
        weight_kg=1.0,
        est_monthly_sales=100,
        target_price_usd=50.0,
        competition_score=0.5,
    )
    base.update(overrides)
    return ProductCandidate(**base)


def test_breakdown_and_profit_math():
    ctx = MarketContext(category="yoga mat", market="US", cny_per_usd=7.2)
    result = ProfitAgent().run(_product(), ctx)

    b = result.breakdown
    # supplier 72/7.2 = 10; refund 13% of 10 = 1.3
    assert b["supplier_cost"] == 10.0
    assert b["export_refund"] == -1.3
    # US: first_leg 1kg*6=6; commission 50*0.15=7.5; fulfillment 3+1*1.2=4.2
    assert b["first_leg_shipping"] == 6.0
    assert b["platform_commission"] == 7.5
    assert b["fulfillment"] == 4.2
    # ad 50*0.15=7.5; returns 50*0.05*0.6=1.5; payment 50*0.01=0.5
    assert b["advertising"] == 7.5
    assert b["returns"] == 1.5
    assert b["payment_fee"] == 0.5
    # total = 10 -1.3 +6 +7.5 +4.2 +7.5 +1.5 +0.5 +0 = 35.9
    assert b["total_cost"] == 35.9
    assert result.unit_profit == 14.1
    assert abs(result.margin_pct - 14.1 / 50.0) < 1e-6
    assert result.monthly_profit == 14.1 * 100


def test_budget_caps_first_order_qty():
    ctx = MarketContext(category="yoga mat", market="US", budget_usd=100.0, cny_per_usd=7.2)
    result = ProfitAgent().run(_product(), ctx)
    # unit capital = supplier 10 + first_leg 6 = 16; 100//16 = 6
    assert result.suggested_first_order_qty == 6
    assert result.first_order_cost == 96.0


def test_low_margin_product_has_small_profit():
    ctx = MarketContext(category="x", market="US", cny_per_usd=7.2)
    p = _product(target_price_usd=20.0, supplier_cost_cny=72.0)
    result = ProfitAgent().run(p, ctx)
    assert result.unit_profit < result.selling_price * 0.2
