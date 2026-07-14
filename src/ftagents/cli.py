"""命令行入口:输入品类 → 输出「能不能做 + 落地利润 + 合规待办」。

用法示例:
    ftagents --category "bluetooth earbuds" --market US --budget 5000
    python -m ftagents.cli --category "yoga mat" --json
"""

from __future__ import annotations

import argparse
import json
import sys

from .datastore import load_products
from .models import MarketContext, PipelineResult, ScoredCandidate, Verdict
from .orchestrator import NoCandidatesError, run_pipeline

_VERDICT_LABEL = {
    Verdict.GO: "✅ 可以做 (GO)",
    Verdict.CAUTION: "⚠️  谨慎评估 (CAUTION)",
    Verdict.NO_GO: "❌ 不建议 (NO-GO)",
}


def _interactive_selector(scored: list[ScoredCandidate]) -> ScoredCandidate:
    print("\n选品结果(按机会分排序),请选择要深入分析的候选:")
    for i, s in enumerate(scored):
        print(f"  [{i}] {s.product.name}  机会分 {s.opportunity_score:.3f}")
    raw = input(f"输入序号 (0-{len(scored) - 1}, 回车默认 0): ").strip()
    if not raw:
        return scored[0]
    try:
        idx = int(raw)
        return scored[idx]
    except (ValueError, IndexError):
        print("输入无效,使用默认 0")
        return scored[0]


def _render(result: PipelineResult) -> str:
    ctx = result.context
    s = result.scored_candidate
    p = s.product
    c = result.compliance
    pr = result.profit
    rec = result.recommendation

    out: list[str] = []
    out.append("=" * 60)
    out.append(f"外贸选品决策报告 | 品类: {ctx.category} | 市场: {ctx.normalized_market()}")
    out.append("=" * 60)
    out.append(f"\n【定案商品】{p.name} ({p.id})")
    out.append(
        f"  机会分 {s.opportunity_score:.3f} | 需求 {s.demand_score:.2f} | "
        f"竞争 {s.competition_score:.2f} | 毛利代理 {s.margin_proxy:.2f}"
    )

    out.append(f"\n【总体结论】{_VERDICT_LABEL[rec.verdict]}")
    for r in rec.reasons:
        out.append(f"  - {r}")

    out.append("\n【落地利润(单位:美元)】")
    out.append(f"  售价 {pr.selling_price} | 单件利润 {pr.unit_profit} | 利润率 {pr.margin_pct:.1%}")
    out.append(f"  预估月利润 {pr.monthly_profit:,.0f} | ROI {pr.roi_pct:.1%}")
    out.append(f"  建议首单 {pr.suggested_first_order_qty} 件,占用资金 ${pr.first_order_cost:,.0f}")
    out.append("  成本构成:")
    for k, v in pr.breakdown.items():
        out.append(f"    {k:<20} {v:>8.2f}")

    out.append(f"\n【合规】状态 {c.status.value}" + ("(阻断)" if c.blocking else ""))
    if c.required_certifications:
        out.append(f"  需认证: {', '.join(c.required_certifications)}")
    if c.restrictions:
        out.append(f"  限制: {'; '.join(c.restrictions)}")
    if c.tax_obligations:
        out.append(f"  税务: {'; '.join(c.tax_obligations)}")
    out.append("  待办:")
    for t in c.todos:
        out.append(f"    - {t}")

    if result.ranked_alternatives:
        out.append("\n【其他候选】")
        for alt in result.ranked_alternatives:
            out.append(f"  - {alt.product.name} (机会分 {alt.opportunity_score:.3f})")

    out.append("\n【摘要】" + ("(LLM 增强)" if result.llm_used else "(模板)"))
    out.append(result.summary)
    out.append("=" * 60)
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ftagents",
        description="外贸最小闭环:选品 + 合规 + 利润测算多 Agent 原型",
    )
    parser.add_argument("--category", "-c", help="目标品类,如 'bluetooth earbuds'")
    parser.add_argument("--market", "-m", default="US", help="目标市场 (US/EU/UK),默认 US")
    parser.add_argument("--budget", "-b", type=float, default=5000.0, help="启动预算(美元),默认 5000")
    parser.add_argument("--cny-per-usd", type=float, default=7.2, help="人民币兑美元汇率,默认 7.2")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--no-llm", action="store_true", help="强制不使用 LLM(纯确定性)")
    parser.add_argument("--interactive", action="store_true", help="交互式选择候选(人工定案)")
    parser.add_argument("--list-categories", action="store_true", help="列出可用示例品类后退出")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_categories:
        cats = sorted({p.category for p in load_products()})
        print("可用示例品类:")
        for cat in cats:
            print(f"  - {cat}")
        return 0

    if not args.category:
        print("错误:请用 --category 指定品类,或用 --list-categories 查看示例。", file=sys.stderr)
        return 2

    ctx = MarketContext(
        category=args.category,
        market=args.market,
        budget_usd=args.budget,
        cny_per_usd=args.cny_per_usd,
    )
    selector = _interactive_selector if args.interactive else None

    try:
        result = run_pipeline(ctx, selector=selector, use_llm=not args.no_llm)
    except NoCandidatesError as exc:
        print(f"错误:{exc}", file=sys.stderr)
        print("提示:用 --list-categories 查看可用示例品类。", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
