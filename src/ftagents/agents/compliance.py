"""合规 Agent:确定性规则库 → 红黄绿灯 + 待办清单。

规则来源:``data/compliance_rules.json``。核心判定不交给大模型,作为护栏。
"""

from __future__ import annotations

from ..datastore import load_compliance_rules
from ..models import ComplianceResult, ComplianceStatus, MarketContext, ProductCandidate

_SEVERITY = {ComplianceStatus.GREEN: 0, ComplianceStatus.YELLOW: 1, ComplianceStatus.RED: 2}


def _escalate(current: ComplianceStatus, target: ComplianceStatus) -> ComplianceStatus:
    return target if _SEVERITY[target] > _SEVERITY[current] else current


class ComplianceAgent:
    def __init__(self, rules: dict | None = None) -> None:
        self._rules = rules if rules is not None else load_compliance_rules()

    def run(self, product: ProductCandidate, ctx: MarketContext) -> ComplianceResult:
        market = ctx.normalized_market()
        categories = self._rules.get("categories", {})
        cat_rule = categories.get(product.category, {})

        status = ComplianceStatus.GREEN
        blocking = False
        todos: list[str] = []
        restrictions: list[str] = []

        # 侵权/品牌风险 -> 红灯,阻断
        ip_risk = bool(product.brand_risk)
        if ip_risk:
            status = _escalate(status, ComplianceStatus.RED)
            blocking = True
            todos.append(
                "存在品牌/侵权风险:上架前完成商标与专利排查,或改用自有品牌/原创设计"
            )

        # 认证要求 -> 黄灯
        certs = list(cat_rule.get("certifications", {}).get(market, []))
        if certs:
            status = _escalate(status, ComplianceStatus.YELLOW)
            todos.append(f"取得 {market} 市场认证:{', '.join(certs)}")

        # 受限类目 -> 黄灯
        if cat_rule.get("restricted"):
            status = _escalate(status, ComplianceStatus.YELLOW)
            note = cat_rule.get("restriction_note", "该类目在部分平台/国家受限")
            restrictions.append(note)
            todos.append("确认目标平台该类目准入资质与邮寄限制")

        # 危险品/特殊属性 -> 黄灯
        hazmat_rules = self._rules.get("hazmat", {})
        for flag in product.hazmat:
            rule = hazmat_rules.get(flag)
            if not rule:
                continue
            status = _escalate(status, ComplianceStatus(rule.get("status", "YELLOW")))
            todos.extend(rule.get("todos", []))

        # 税务义务(通用,不改变红黄绿灯颜色)
        tax_obligations = list(self._rules.get("market_tax", {}).get(market, []))

        if status == ComplianceStatus.GREEN and not todos:
            todos.append("基础合规,按平台常规资质上架即可")

        return ComplianceResult(
            status=status,
            blocking=blocking,
            required_certifications=certs,
            restrictions=restrictions,
            ip_risk=ip_risk,
            tax_obligations=tax_obligations,
            todos=todos,
        )
