from __future__ import annotations

import asyncio
import os

import aiohttp

from qa_bot.security import redact


async def send_admin_notification(text: str, *, token: str | None = None, admin_id: str | None = None, retries: int = 2, timeout_seconds: int = 10) -> bool:
    secret = token if token is not None else os.getenv("QA_BOT_TOKEN", "").strip()
    recipient = admin_id if admin_id is not None else os.getenv("QA_ADMIN_TELEGRAM_ID", "").strip()
    if not secret or not recipient:
        return False
    payload = {"chat_id": recipient, "text": redact(text)[:4000], "disable_web_page_preview": True}
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    for attempt in range(max(1, retries)):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"https://api.telegram.org/bot{secret}/sendMessage", json=payload) as response:
                    if response.status < 400:
                        return True
        except Exception:
            pass
        if attempt + 1 < retries:
            await asyncio.sleep(1)
    return False
