from dataclasses import dataclass
from typing import Optional

@dataclass
class AccountConfig:
    name: str
    vertical: str
    base_url: str
    auth_type: str
    client_id: str
    client_secret: str

@dataclass
class TokenInfo:
    access_token: str
    expires_at: float  # Unix epoch seconds

@dataclass
class ActivityRow:
    account_name: str
    vertical: str
    client_id: str
    downloaded_at: int
    activity_timestamp: Optional[int]
    activity_id: Optional[int]
    dedupe_key: str
    activity_body: str  # JSON string
