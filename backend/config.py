import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    twilio_account_sid: str = field(
        default_factory=lambda: os.environ.get("TWILIO_ACCOUNT_SID", "")
    )
    twilio_auth_token: str = field(
        default_factory=lambda: os.environ.get("TWILIO_AUTH_TOKEN", "")
    )
    twilio_phone_number: str = field(
        default_factory=lambda: os.environ.get("TWILIO_PHONE_NUMBER", "")
    )
    host: str = "0.0.0.0"
    port: int = 8000
