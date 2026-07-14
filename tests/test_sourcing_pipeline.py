import pytest

from ftagents.agents import SourcingAgent
from ftagents.models import MarketContext, Verdict
from ftagents.orchestrator import NoCandidatesError, run_pipeline


def test_sourcing_matches_category_and_ranks():
    ctx = MarketContext(category="yoga mat", market="US")
    scored = SourcingAgent().run(ctx)
    assert scored, "should find yoga mat candidates"
    assert all("yoga mat" in s.product.category for s in scored)
    # sorted by opportunity_score desc
    scores = [s.opportunity_score for s in scored]
    assert scores == sorted(scores, reverse=True)


def test_sourcing_respects_market_availability():
    # UK not listed for the natural-rubber mat (YM-002)
    ctx = MarketContext(category="yoga mat", market="UK")
    scored = SourcingAgent().run(ctx)
    ids = {s.product.id for s in scored}
    assert "YM-002" not in ids
    assert "YM-001" in ids


def test_no_candidates_raises():
    ctx = MarketContext(category="nonexistent-category-xyz", market="US")
    with pytest.raises(NoCandidatesError):
        run_pipeline(ctx, use_llm=False)


def test_pipeline_go_for_healthy_product():
    ctx = MarketContext(category="silicone kitchen utensils", market="US")
    result = run_pipeline(ctx, use_llm=False)
    assert result.profit.margin_pct > 0
    assert result.recommendation.verdict in {Verdict.GO, Verdict.CAUTION}
    assert result.summary
    assert not result.llm_used


def test_pipeline_no_go_for_brand_risk_product():
    ctx = MarketContext(category="kids building blocks", market="US")
    result = run_pipeline(ctx, use_llm=False)
    assert result.compliance.blocking
    assert result.recommendation.verdict == Verdict.NO_GO


def test_pipeline_result_is_json_serializable():
    import json

    ctx = MarketContext(category="yoga mat", market="US")
    result = run_pipeline(ctx, use_llm=False)
    payload = json.dumps(result.to_dict(), ensure_ascii=False)
    assert "recommendation" in payload
