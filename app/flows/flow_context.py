from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class FlowContext:
    correlation_id: str
    phone: Optional[str] = None
    message_id: Optional[str] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "phone": self.phone,
            "message_id": self.message_id,
            "request_path": self.request_path,
            "request_method": self.request_method,
        }

