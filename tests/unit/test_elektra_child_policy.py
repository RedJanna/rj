import pytest

from app.services.elektraweb_booking_service import (
    _clear_child_age_payload_fields,
    _apply_child_policy_to_pricing,
    _extract_child_ages,
    _extract_price_data_pax_counts,
)


@pytest.mark.unit
def test_extract_child_ages_supports_multi_age_list():
    assert _extract_child_ages("2 cocuk 10 ve 3 yas") == [10, 3]


@pytest.mark.unit
def test_extract_child_ages_supports_multi_age_with_repeated_yas_words():
    assert _extract_child_ages("2 cocuk 10 yas ve 8 yas") == [10, 8]


@pytest.mark.unit
def test_extract_child_ages_supports_monthly_baby_as_zero_age():
    assert _extract_child_ages("1 bebek 9 aylik") == [0]


@pytest.mark.unit
def test_policy_keeps_age_over_five_as_child_for_pricing():
    pricing_adult, pricing_child_ages = _apply_child_policy_to_pricing(2, [10])
    assert pricing_adult == 2
    assert pricing_child_ages == [10]


@pytest.mark.unit
def test_policy_keeps_all_child_ages_for_pricing():
    pricing_adult, pricing_child_ages = _apply_child_policy_to_pricing(2, [10, 3])
    assert pricing_adult == 2
    assert pricing_child_ages == [10, 3]


@pytest.mark.unit
def test_policy_keeps_multiple_children_without_adult_conversion():
    pricing_adult, pricing_child_ages = _apply_child_policy_to_pricing(2, [10, 11])
    assert pricing_adult == 2
    assert pricing_child_ages == [10, 11]


@pytest.mark.unit
def test_policy_converts_age_17_to_adult():
    pricing_adult, pricing_child_ages = _apply_child_policy_to_pricing(2, [17, 10])
    assert pricing_adult == 3
    assert pricing_child_ages == [10]


@pytest.mark.unit
def test_extract_price_data_pax_counts_parses_concatenated_error_text():
    txt = (
        "adult-count and children counts (elder/younger/baby) doesn't match with price data, "
        "as found adult: 4, and elder-child-count: 0younger-child-count: 0baby-count: 0"
    )
    assert _extract_price_data_pax_counts(txt) == {
        "adult": 4,
        "elder-child-count": 0,
        "younger-child-count": 0,
        "baby-count": 0,
    }


@pytest.mark.unit
def test_clear_child_age_payload_fields_removes_all_child_age_keys():
    payload = {
        "childage": "10,3",
        "child-age": "10,3",
        "child-ages": "10,3",
        "child-age-list": [10, 3],
        "child-age-arr": [10, 3],
        "children-ages": [10, 3],
        "child-1-age": 10,
        "child-age-1": 10,
        "child-2-age": 3,
        "child-age-2": 3,
        "child": 2,
        "child-count": 2,
    }
    _clear_child_age_payload_fields(payload)
    assert "childage" not in payload
    assert "child-age" not in payload
    assert "child-ages" not in payload
    assert "child-age-list" not in payload
    assert "child-age-arr" not in payload
    assert "children-ages" not in payload
    assert "child-1-age" not in payload
    assert "child-age-1" not in payload
    assert "child-2-age" not in payload
    assert "child-age-2" not in payload
    # Count alanlari intentionally korunur.
    assert payload["child"] == 2
    assert payload["child-count"] == 2
