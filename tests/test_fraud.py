from app.ai.fraud_detector import HIGH, NORMAL, detect_anomalies, merchant_key
from app.services.demo_data_service import PersonaParams, generate_records
from app.services.transaction_service import documents_to_dataframe


def test_injected_anomalies_are_flagged():
    df = documents_to_dataframe(generate_records(months=12, seed=11))
    report = detect_anomalies(df, save_model=False)
    flagged = {r.description for r in report.flagged_results}
    assert "Croma electronics - card purchase" in flagged
    assert report.method.startswith("Isolation Forest")
    assert report.flagged <= report.analyzed * 0.05  # flags stay rare


def test_recurring_rent_is_normal():
    df = documents_to_dataframe(generate_records(months=12, seed=11))
    report = detect_anomalies(df, save_model=False)
    rent = [r for r in report.results if r.category == "Rent"]
    assert rent and all(r.label == NORMAL for r in rent)


def test_clean_history_has_few_flags():
    df = documents_to_dataframe(generate_records(months=12, seed=3, params=PersonaParams(inject_anomalies=False)))
    report = detect_anomalies(df, save_model=False)
    assert sum(1 for r in report.results if r.label == HIGH) <= 2


def test_flags_have_reasons_and_never_claim_fraud():
    df = documents_to_dataframe(generate_records(months=12, seed=11))
    for r in detect_anomalies(df, save_model=False).flagged_results:
        assert r.reasons
        assert "fraud" not in r.label.lower()


def test_small_history_uses_rules_and_empty_is_safe():
    small = documents_to_dataframe(generate_records(months=1, seed=1))[:10]
    assert "rules" in detect_anomalies(small, save_model=False).method
    assert detect_anomalies(documents_to_dataframe([]), save_model=False).analyzed == 0


def test_merchant_key():
    assert merchant_key("Swiggy order 8841") == "swiggy order"
    assert merchant_key("12345") == "unknown"
