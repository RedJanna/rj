from app.services.intent_router_service import infer_domain_hint, route_intent


def test_infer_domain_hint_payment():
    assert infer_domain_hint("online odeme baglantisi iletebilir misiniz") == "payment"


def test_infer_domain_hint_unknown():
    assert infer_domain_hint("merhaba") == "unknown"


def test_route_intent_has_shape():
    result = route_intent("fiyat alabilir miyim", "hotel")
    assert "primary_intent" in result
    assert result["domain_hint"] == "hotel"
    assert "semantic_confidence" in result
    assert isinstance(result["semantic_confidence"], float)
    assert result["router"] == "intent_router_v1"


def test_infer_domain_hint_hotel_with_semantic_sentence():
    assert infer_domain_hint("14-18 agustos icin toplam konaklama bedeli nedir") == "hotel"
