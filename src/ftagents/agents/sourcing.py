"""选品 Agent:按品类/预算/市场筛选并打分。

评分是确定性的:综合"需求、竞争、毛利代理指标"三项加权。
"""

from __future__ import annotations

from ..datastore import load_products
from ..models import MarketContext, ProductCandidate, ScoredCandidate

# 评分权重
_W_DEMAND = 0.4
_W_COMPETITION = 0.3
_W_MARGIN = 0.3


class SourcingAgent:
    def __init__(self, products: list[ProductCandidate] | None = None) -> None:
        self._products = products if products is not None else load_products()

    def _matches(self, product: ProductCandidate, ctx: MarketContext) -> bool:
        cat = ctx.category.strip().lower()
        pcat = product.category.lower()
        if cat and cat not in pcat and pcat not in cat:
            return False
        if product.markets and ctx.normalized_market() not in product.markets:
            return False
        return True

    def run(self, ctx: MarketContext) -> list[ScoredCandidate]:
        candidates = [p for p in self._products if self._matches(p, ctx)]
        if not candidates:
            return []

        max_sales = max(p.est_monthly_sales for p in candidates) or 1
        scored: list[ScoredCandidate] = []
        for p in candidates:
            supplier_usd = p.supplier_cost_cny / ctx.cny_per_usd
            demand = p.est_monthly_sales / max_sales
            margin_proxy = 0.0
            if p.target_price_usd > 0:
                margin_proxy = max(
                    0.0, (p.target_price_usd - supplier_usd) / p.target_price_usd
                )
            opportunity = (
                _W_DEMAND * demand
                + _W_COMPETITION * (1.0 - p.competition_score)
                + _W_MARGIN * margin_proxy
            )
            scored.append(
                ScoredCandidate(
                    product=p,
                    demand_score=round(demand, 4),
                    competition_score=p.competition_score,
                    margin_proxy=round(margin_proxy, 4),
                    opportunity_score=round(opportunity, 4),
                )
            )

        scored.sort(key=lambda s: s.opportunity_score, reverse=True)
        return scored
