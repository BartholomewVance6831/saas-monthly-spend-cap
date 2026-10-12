from src.spend_cap_service import decide_spend


def test_request_over_cap_is_rejected_before_provider_call() -> None:
    decision = decide_spend(hard_cap_usd=100.0, spent_usd=91.25, requested_usd=9.0)
    assert decision.allowed is False
    assert decision.remaining_usd == 8.75
    assert decision.reason == "request would exceed monthly hard cap"
