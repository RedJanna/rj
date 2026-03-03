from app.services.intent_semantic_service import infer_intent_semantic


def test_external_scenario_examples_are_used_for_payment_link_request():
    intent, score = infer_intent_semantic("Ön ödemeyi online yapmak istiyorum, bağlantı atar mısınız?")
    assert intent == "PAYMENT_LINK_REQUEST"
    assert score >= 0.22


def test_external_scenario_examples_are_used_for_human_agent_request():
    intent, score = infer_intent_semantic("Operatörle görüşebilir miyim?")
    assert intent == "HUMAN_AGENT_REQUEST"
    assert score >= 0.22
