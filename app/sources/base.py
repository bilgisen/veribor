"""Kaynak sözleşmesi — finveri SourceResult ile aynı felsefe."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class SourceResult:
    success: bool
    data: Optional[list[dict[str, Any]]] = field(default=None)
    error: Optional[str] = None
    fetched_at: Optional[datetime] = None

    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.now(timezone.utc)
