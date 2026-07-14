from __future__ import annotations

from typing import Mapping


def format_alert(alert: Mapping[str, object], language: str = "English", *, delete_prefix: bool = False) -> str:
    condition = str(alert["condition"])
    word = ("вище" if condition == ">" else "нижче") if language == "Ukrainian" else ("above" if condition == ">" else "below")
    price = float(alert["target_price"])
    value = f"${price:,.2f}".rstrip("0").rstrip(".")
    if language == "Ukrainian":
        value = value.replace(",", " ")
    prefix = "🗑 " if delete_prefix else ""
    return f"{prefix}{alert['coin']} {word} {value}"
