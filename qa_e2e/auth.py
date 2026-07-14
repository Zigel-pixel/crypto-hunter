from __future__ import annotations

import getpass
from typing import Any, Callable

from qa_e2e.client import create_telethon_client
from qa_e2e.config import E2EConfig


class AuthorizationError(RuntimeError):
    pass


async def authorize(config: E2EConfig, *, client: Any | None = None, code_reader: Callable[[str], str] = input, password_reader: Callable[[str], str] = getpass.getpass) -> bool:
    telegram = client or create_telethon_client(config)
    await telegram.connect()
    try:
        if await telegram.is_user_authorized():
            return True
        sent = await telegram.send_code_request(config.phone)
        code = code_reader("Telegram login code (local console only): ").strip()
        if not code:
            raise AuthorizationError("Authorization code was not provided")
        try:
            await telegram.sign_in(config.phone, code, phone_code_hash=getattr(sent, "phone_code_hash", None))
        except Exception as exc:
            try:
                from telethon.errors import SessionPasswordNeededError
                needs_password = isinstance(exc, SessionPasswordNeededError) or type(exc).__name__ == "SessionPasswordNeededError"
            except ImportError:
                needs_password = type(exc).__name__ == "SessionPasswordNeededError"
            if not needs_password:
                raise AuthorizationError(f"Telegram authorization failed ({type(exc).__name__})") from exc
            password = password_reader("Telegram 2FA password: ")
            if not password:
                raise AuthorizationError("Two-factor password was not provided")
            try:
                await telegram.sign_in(password=password)
            finally:
                password = ""
        return bool(await telegram.is_user_authorized())
    finally:
        await telegram.disconnect()
