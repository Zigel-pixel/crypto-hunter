from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from telethon.tl import types as tl_types


class UnsafeButtonError(RuntimeError):
    pass


def normalize_label(value: str) -> str:
    return " ".join(value.casefold().split())


def inline_buttons(message: Any) -> tuple[Any, ...]:
    if not _is_markup(message, tl_types.ReplyInlineMarkup):
        return ()
    rows = getattr(message, "buttons", None) or ()
    return tuple(button for row in rows for button in (row if isinstance(row, (list, tuple)) else (row,)))


def button_labels(message: Any) -> tuple[str, ...]:
    return tuple(str(getattr(button, "text", "")) for button in inline_buttons(message) if getattr(button, "text", None))


def find_inline_button(message: Any, *, text: str | None = None, callback_prefix: bytes | str | None = None) -> Any:
    wanted = normalize_label(text) if text else None
    prefix = callback_prefix.encode() if isinstance(callback_prefix, str) else callback_prefix
    for button in inline_buttons(message):
        label = str(getattr(button, "text", ""))
        data = getattr(button, "data", None)
        if (wanted is None or normalize_label(label) == wanted) and (prefix is None or isinstance(data, bytes) and data.startswith(prefix)):
            ensure_safe_button(button)
            return button
    raise LookupError("Requested safe inline button was not found")


def ensure_safe_button(button: Any) -> None:
    if any(getattr(button, name, None) for name in ("url", "login_url", "webview", "web_app")):
        raise UnsafeButtonError("URL, login, and Web App buttons are forbidden")
    if getattr(button, "buy", False) or getattr(button, "payment", False):
        raise UnsafeButtonError("Payment buttons are forbidden")


def reply_keyboard_labels(message: Any) -> tuple[str, ...]:
    markup = getattr(message, "reply_markup", None)
    if not isinstance(markup, tl_types.ReplyKeyboardMarkup):
        return ()
    rows = getattr(markup, "rows", None) or ()
    labels: list[str] = []
    for row in rows:
        for button in getattr(row, "buttons", ()):
            text = getattr(button, "text", None)
            if text: labels.append(str(text))
    return tuple(labels)


def _is_markup(message: Any, markup_type: type[Any]) -> bool:
    """Classify by Telegram markup type, never by visible button shape/text."""
    return isinstance(getattr(message, "reply_markup", None), markup_type)


def select_reply_label(message: Any, candidates: tuple[str, ...]) -> str:
    available = {normalize_label(label): label for label in reply_keyboard_labels(message)}
    for candidate in candidates:
        if normalize_label(candidate) in available:
            return available[normalize_label(candidate)]
    raise LookupError("Requested reply-keyboard action is unavailable")
