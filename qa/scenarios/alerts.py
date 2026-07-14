from app.keyboards.alerts import build_delete_alert_keyboard
from app.services.alert_formatter import format_alert
from qa_bot.models import Scenario


async def formatting_check():
    alert = {"id": 9, "coin": "BTC", "condition": ">", "target_price": 70000.0}
    button = build_delete_alert_keyboard([alert]).inline_keyboard[0][0]
    ok = "BTC above $70,000" in button.text and button.callback_data == "alert:delete:select:9" and "вище" in format_alert(alert, "Ukrainian")
    return ok, f"{button.text} · {button.callback_data}", "Stable owner-scoped deletion is verified separately by unit tests"


def scenarios():
    return (Scenario("alerts.delete_format", "Descriptive stable alert deletion", "alerts", "Build English/Ukrainian alert deletion labels and callback.", "Descriptive text and stable ID callback", formatting_check, related_modules=("app/services/alert_formatter.py", "app/keyboards/alerts.py")),)
