"""共享状态数据模型。

这些 dataclass 是各 Agent 之间传递的"产品档案 / 目标市场 / 结果"载体,
对应设计文档里的"共享状态"。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    """整体结论。"""

    GO = "GO"
    CAUTION = "CAUTION"
    NO_GO = "NO-GO"


class ComplianceStatus(str, Enum):
    """合规红黄绿灯。"""

    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


@dataclass
class MarketContext:
    """一次分析的输入上下文。"""

    category: str
    market: str = "US"
    budget_usd: float = 5000.0
    cny_per_usd: float = 7.2

    def normalized_market(self) -> str:
        return self.market.strip().upper()


@dataclass
class ProductCandidate:
    """候选商品(来自选品数据源)。"""

    id: str
    name: str
    category: str
    supplier_cost_cny: float
    weight_kg: float
    est_monthly_sales: int
    target_price_usd: float
    competition_score: float  # 0(无竞争)~ 1(极度红海)
    avg_review_count: int = 0
    hazmat: list[str] = field(default_factory=list)  # e.g. ["battery", "liquid"]
    brand_risk: bool = False  # 是否存在明显品牌/侵权风险
    markets: list[str] = field(default_factory=list)  # 有数据的目标市场
    notes: str = ""


@dataclass
class ScoredCandidate:
    """带评分的候选(选品 Agent 产出)。"""

    product: ProductCandidate
    demand_score: float
    competition_score: float
    margin_proxy: float
    opportunity_score: float


@dataclass
class ComplianceResult:
    """合规 Agent 产出。"""

    status: ComplianceStatus
    blocking: bool
    required_certifications: list[str] = field(default_factory=list)
    restrictions: list[str] = field(default_factory=list)
    ip_risk: bool = False
    tax_obligations: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)


@dataclass
class ProfitResult:
    """利润测算 Agent 产出(单位:美元)。"""

    selling_price: float
    breakdown: dict[str, float]
    unit_profit: float
    margin_pct: float
    monthly_profit: float
    roi_pct: float
    suggested_first_order_qty: int
    first_order_cost: float


@dataclass
class Recommendation:
    verdict: Verdict
    reasons: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """一次完整闭环的聚合结果。"""

    context: MarketContext
    scored_candidate: ScoredCandidate
    compliance: ComplianceResult
    profit: ProfitResult
    recommendation: Recommendation
    summary: str = ""
    ranked_alternatives: list[ScoredCandidate] = field(default_factory=list)
    llm_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _to_jsonable(asdict(self))


def _to_jsonable(obj: Any) -> Any:
    """把 Enum 递归转成其字符串值,便于 JSON 序列化。"""

    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, Enum):
        return obj.value
    return obj
