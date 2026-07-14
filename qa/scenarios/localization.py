from __future__ import annotations

from app.keyboards.alerts import build_alerts_keyboard
from app.keyboards.consultant import build_consultant_keyboard
from app.keyboards.main import build_main_keyboard
from app.keyboards.wallet import build_wallet_detail_keyboard
from app.utils.i18n import translate
from qa_bot.models import Scenario


async def keyboard_check():
    en = {b.text for row in build_main_keyboard("English").keyboard for b in row}
    uk = {b.text for row in build_main_keyboard("Ukrainian").keyboard for b in row}
    nested = {b.text for row in build_alerts_keyboard("Ukrainian").keyboard for b in row} | {b.text for row in build_consultant_keyboard("Ukrainian").keyboard for b in row}
    ok = "📊 Assets" in en and "📊 Активи" in uk and "🗑 Видалити сповіщення" in nested
    return ok, "English/Ukrainian keyboards use centralized resources", "Main and nested keyboard labels checked"


async def stable_callback_check():
    callback = build_wallet_detail_keyboard(12, "Ukrainian").inline_keyboard[0][0].callback_data
    return callback == "wallet:refresh:12", f"Callback: {callback}", "Visible language does not alter callback identifiers"


def scenarios():
    return (
        Scenario("localization.keyboards", "Localized keyboard resources", "localization", "Build current English and Ukrainian keyboards.", "Known translated controls are present", keyboard_check, related_modules=("app/utils/i18n.py",)),
        Scenario("localization.callbacks", "Language-independent callbacks", "localization", "Build an old-style wallet detail callback in Ukrainian.", "Stable callback remains wallet:refresh:12", stable_callback_check, related_modules=("app/keyboards/wallet.py",)),
    )
