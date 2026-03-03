from app.services.error_code_service import derive_error_code
from app.services import system_health_service as sh


def test_derive_error_code_timeout():
    code = derive_error_code(event="chat.openai.error", error_type="TimeoutError", message="request timed out")
    assert code == "E_CHAT_TIMEOUT"


def test_derive_error_code_openai_failure():
    code = derive_error_code(event="chat.openai.error", error_type="APIConnectionError", message="openai connection refused")
    assert code == "E_OPENAI_FAIL"


def test_system_health_log_error_persists_code():
    sh.clear_error_logs()
    sh.log_error("chat_error", "openai request timed out")
    assert sh.ERROR_LOGS
    assert sh.ERROR_LOGS[-1]["code"] == "E_CHAT_TIMEOUT"
