"""Orchestrator:把三个 Agent 串成流水线,并保留人工定案节点。

流程:选品 → (人工/默认)定案 → 合规 + 利润测算 并行产出 → 综合结论 → 摘要。
综合结论用确定性阈值做护栏;摘要在有 LLM 时增强,否则用模板。
"""

from __future__ import annotations

from typing import Callable

from .agents import ComplianceAgent, ProfitAgent, SourcingAgent
from .llm import LLMClient
from .models import (
    ComplianceResult,
    ComplianceStatus,
    MarketContext,
    PipelineResult,
    ProfitResult,
    Recommendation,
    ScoredCandidate,
    Verdict,
)

# 利润护栏阈值
_MIN_MARGIN = 0.10
_HEALTHY_MARGIN = 0.20
_RED_OCEAN_COMPETITION = 0.8

Selector = Callable[[list[ScoredCandidate]], ScoredCandidate]


class NoCandidatesError(Exception):
    """选品阶段没有匹配到任何商品。"""


def _default_selector(scored: list[ScoredCandidate]) -> ScoredCandidate:
    return scored[0]


def _decide(
    scored: ScoredCandidate, compliance: ComplianceResult, profit: ProfitResult
) -> Recommendation:
    reasons: list[str] = []

    if compliance.blocking:
        reasons.append("合规红灯(存在阻断性风险,如侵权/受限),不建议推进")
        return Recommendation(verdict=Verdict.NO_GO, reasons=reasons)

    if profit.margin_pct < _MIN_MARGIN:
        reasons.append(
            f"落地利润率仅 {profit.margin_pct:.1%},低于 {_MIN_MARGIN:.0%} 红线,不划算"
        )
        return Recommendation(verdict=Verdict.NO_GO, reasons=reasons)

    caution: list[str] = []
    if compliance.status == ComplianceStatus.YELLOW:
        caution.append("合规黄灯:需先完成认证/资质等待办")
    if profit.margin_pct < _HEALTHY_MARGIN:
        caution.append(f"利润率 {profit.margin_pct:.1%} 偏薄,抗风险能力弱")
    if scored.competition_score >= _RED_OCEAN_COMPETITION:
        caution.append("竞争激烈(红海),获客成本可能高于预估")

    if caution:
        return Recommendation(verdict=Verdict.CAUTION, reasons=caution)

    reasons.append(
        f"利润率 {profit.margin_pct:.1%}、月利润约 ${profit.monthly_profit:,.0f},合规可控"
    )
    return Recommendation(verdict=Verdict.GO, reasons=reasons)


def _template_summary(result_parts: dict) -> str:
    ctx: MarketContext = result_parts["ctx"]
    scored: ScoredCandidate = result_parts["scored"]
    compliance: ComplianceResult = result_parts["compliance"]
    profit: ProfitResult = result_parts["profit"]
    rec: Recommendation = result_parts["rec"]
    p = scored.product
    lines = [
        f"结论:{rec.verdict.value} —— {p.name}({ctx.normalized_market()} 市场)",
        f"落地利润:单件 ${profit.unit_profit:.2f}、利润率 {profit.margin_pct:.1%}、"
        f"预估月利润 ${profit.monthly_profit:,.0f}、ROI {profit.roi_pct:.1%}",
        f"合规:{compliance.status.value}"
        + (f",阻断项:{'; '.join(compliance.restrictions) or '侵权风险'}" if compliance.blocking else ""),
        "理由:" + ";".join(rec.reasons),
    ]
    if compliance.todos:
        lines.append("待办:" + " / ".join(compliance.todos[:4]))
    return "\n".join(lines)


def _llm_summary(llm: LLMClient, result_parts: dict) -> str | None:
    ctx: MarketContext = result_parts["ctx"]
    scored: ScoredCandidate = result_parts["scored"]
    compliance: ComplianceResult = result_parts["compliance"]
    profit: ProfitResult = result_parts["profit"]
    rec: Recommendation = result_parts["rec"]
    p = scored.product
    prompt = (
        "根据以下结构化分析,用中文写 4-6 句话的决策摘要,包含:是否值得做、"
        "关键利润数字、主要风险与下一步动作。不要编造数据。\n\n"
        f"目标市场: {ctx.normalized_market()}\n"
        f"商品: {p.name}(品类 {p.category})\n"
        f"系统结论: {rec.verdict.value}\n"
        f"单件利润: ${profit.unit_profit:.2f}, 利润率: {profit.margin_pct:.1%}, "
        f"月利润: ${profit.monthly_profit:.0f}, ROI: {profit.roi_pct:.1%}\n"
        f"成本构成: {profit.breakdown}\n"
        f"合规状态: {compliance.status.value}, 待办: {compliance.todos}\n"
        f"系统理由: {rec.reasons}\n"
    )
    return llm.complete(prompt)


def run_pipeline(
    ctx: MarketContext,
    *,
    selector: Selector | None = None,
    use_llm: bool = True,
    llm: LLMClient | None = None,
) -> PipelineResult:
    sourcing = SourcingAgent()
    scored_all = sourcing.run(ctx)
    if not scored_all:
        raise NoCandidatesError(f"没有匹配品类「{ctx.category}」的候选商品")

    selector = selector or _default_selector
    chosen = selector(scored_all)

    compliance = ComplianceAgent().run(chosen.product, ctx)
    profit = ProfitAgent().run(chosen.product, ctx)
    rec = _decide(chosen, compliance, profit)

    parts = {"ctx": ctx, "scored": chosen, "compliance": compliance, "profit": profit, "rec": rec}

    llm_used = False
    summary = None
    if use_llm:
        client = llm or LLMClient()
        if client.available:
            summary = _llm_summary(client, parts)
            llm_used = summary is not None
    if not summary:
        summary = _template_summary(parts)

    alternatives = [s for s in scored_all if s is not chosen]
    return PipelineResult(
        context=ctx,
        scored_candidate=chosen,
        compliance=compliance,
        profit=profit,
        recommendation=rec,
        summary=summary,
        ranked_alternatives=alternatives,
        llm_used=llm_used,
    )
