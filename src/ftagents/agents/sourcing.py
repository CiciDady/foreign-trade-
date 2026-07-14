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


def score_candidate(
    product: ProductCandidate, ctx: MarketContext, max_sales: int
) -> ScoredCandidate:
    """对单个商品打分。``max_sales`` 用于需求归一化(同一批次内取最大值)。"""

    supplier_usd = product.supplier_cost_cny / ctx.cny_per_usd
    demand = product.est_monthly_sales / max_sales if max_sales else 0.0
    demand = min(1.0, max(0.0, demand))
    margin_proxy = 0.0
    if product.target_price_usd > 0:
        margin_proxy = max(0.0, (product.target_price_usd - supplier_usd) / product.target_price_usd)
    opportunity = (
        _W_DEMAND * demand
        + _W_COMPETITION * (1.0 - product.competition_score)
        + _W_MARGIN * margin_proxy
    )
    return ScoredCandidate(
        product=product,
        demand_score=round(demand, 4),
        competition_score=product.competition_score,
        margin_proxy=round(margin_proxy, 4),
        opportunity_score=round(opportunity, 4),
    )


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
        scored = [score_candidate(p, ctx, max_sales) for p in candidates]
        scored.sort(key=lambda s: s.opportunity_score, reverse=True)
        return scored
