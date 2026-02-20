import pytest

from app.services import elektra_hoteladvisor_service as svc


@pytest.mark.unit
def test_get_hoteladvisor_path_select_known_endpoint():
    assert svc.get_hoteladvisor_path("select", "QA_HOTEL_RES_GUEST") == "/Select/QA_HOTEL_RES_GUEST"


@pytest.mark.unit
def test_get_hoteladvisor_path_execute_known_endpoint():
    assert svc.get_hoteladvisor_path("execute", "SP_HOTELRESGUEST_SAVE") == "/Execute/SP_HOTELRESGUEST_SAVE"


@pytest.mark.unit
def test_get_hoteladvisor_path_unknown_endpoint_raises():
    with pytest.raises(ValueError):
        svc.get_hoteladvisor_path("select", "UNKNOWN_OBJECT")


@pytest.mark.unit
def test_list_hoteladvisor_endpoints_contains_expected_groups():
    data = svc.list_hoteladvisor_endpoints()
    assert "select" in data
    assert "execute" in data
    assert "QA_HOTEL_RES_GUEST" in data["select"]
    assert "SP_PORTALV4_GETPORTAL_INSTALLMENT" in data["execute"]
