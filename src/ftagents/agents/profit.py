"""利润测算 Agent:把成本/头程/佣金/广告/退货/退税等算进"落地利润"。

所有金额单位为美元。公式确定性,便于审计与单测。
"""

from __future__ import annotations

from ..datastore import load_fees
from ..models import MarketContext, ProductCandidate, ProfitResult


class ProfitAgent:
    def __init__(self, fees: dict | None = None) -> None:
        self._fees = fees if fees is not None else load_fees()

    def run(self, product: ProductCandidate, ctx: MarketContext) -> ProfitResult:
        market = ctx.normalized_market()
        markets = self._fees.get("markets", {})
        m = markets.get(market) or markets.get("US")

        price = product.target_price_usd
        supplier_usd = product.supplier_cost_cny / ctx.cny_per_usd
        export_refund = supplier_usd * self._fees.get("export_refund_rate", 0.0)

        first_leg = product.weight_kg * m["first_leg_rate_per_kg"]
        commission = price * m["commission_rate"]
        fulfillment = m["fulfillment_base"] + product.weight_kg * m["fulfillment_per_kg"]
        ad_cost = price * m["acos"]
        return_cost = price * m["return_rate"] * m["return_loss_factor"]
        payment_fee = price * self._fees.get("payment_fee_rate", 0.0)
        import_tax = price * m.get("import_tax_rate", 0.0)

        # 退税作为供货成本的返还(负成本)
        net_supplier = supplier_usd - export_refund

        total_cost = (
            net_supplier
            + first_leg
            + commission
            + fulfillment
            + ad_cost
            + return_cost
            + payment_fee
            + import_tax
        )
        unit_profit = price - total_cost
        margin_pct = unit_profit / price if price else 0.0
        monthly_profit = unit_profit * product.est_monthly_sales

        # 单件占用资金(采购+头程),用于 ROI
        unit_capital = supplier_usd + first_leg
        roi_pct = unit_profit / unit_capital if unit_capital else 0.0

        qty = int(self._fees.get("default_first_order_qty", 200))
        first_order_cost = unit_capital * qty
        if ctx.budget_usd and first_order_cost > ctx.budget_usd and unit_capital > 0:
            qty = max(1, int(ctx.budget_usd // unit_capital))
            first_order_cost = unit_capital * qty

        breakdown = {
            "supplier_cost": round(supplier_usd, 2),
            "export_refund": -round(export_refund, 2),
            "first_leg_shipping": round(first_leg, 2),
            "platform_commission": round(commission, 2),
            "fulfillment": round(fulfillment, 2),
            "advertising": round(ad_cost, 2),
            "returns": round(return_cost, 2),
            "payment_fee": round(payment_fee, 2),
            "import_tax": round(import_tax, 2),
            "total_cost": round(total_cost, 2),
        }

        return ProfitResult(
            selling_price=round(price, 2),
            breakdown=breakdown,
            unit_profit=round(unit_profit, 2),
            margin_pct=round(margin_pct, 4),
            monthly_profit=round(monthly_profit, 2),
            roi_pct=round(roi_pct, 4),
            suggested_first_order_qty=qty,
            first_order_cost=round(first_order_cost, 2),
        )
