from __future__ import annotations

import logging

from twilio.rest import Client

log = logging.getLogger(__name__)


class TwilioConfigurator:
    def __init__(self, account_sid: str, auth_token: str, phone_number: str) -> None:
        self._client = Client(account_sid, auth_token) if account_sid else None
        self._phone_number = phone_number

    async def set_webhook(self, ngrok_url: str, fallback_url: str) -> None:
        if not self._client:
            log.warning("Twilio not configured, skipping webhook update")
            return
        # Find the phone number SID
        numbers = self._client.incoming_phone_numbers.list(
            phone_number=self._phone_number
        )
        if not numbers:
            log.error(f"Phone number {self._phone_number} not found")
            return
        number = numbers[0]
        webhook_url = f"https://{ngrok_url}/twilio/voice"
        number.update(
            voice_url=webhook_url,
            voice_method="POST",
            voice_fallback_url=fallback_url,
            voice_fallback_method="POST",
        )
        log.info(f"Twilio webhook set to {webhook_url}")

    async def clear_webhook(self, fallback_url: str) -> None:
        if not self._client:
            return
        numbers = self._client.incoming_phone_numbers.list(
            phone_number=self._phone_number
        )
        if not numbers:
            return
        numbers[0].update(
            voice_url=fallback_url,
            voice_method="POST",
        )
        log.info("Twilio webhook cleared to fallback")
