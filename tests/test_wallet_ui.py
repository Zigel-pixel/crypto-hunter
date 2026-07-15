from app.handlers.wallet import _format_decimal, _profile_text
from app.keyboards.wallet import build_wallet_delete_confirmation, build_wallet_detail_keyboard
from app.models.wallet import WalletProfile


def test_decimal_and_stale_profile_rendering_is_localized() -> None:
    profile = WalletProfile(7, "0x" + "a" * 40, "evm", "Основний", ("ethereum",),
                            "2026-01-01", "2026-01-01", "0.00003400", "125.5000", "ETH", "stale", "timeout")
    assert _format_decimal(profile.native_balance) == "0.000034"
    uk = _profile_text(profile, "Ukrainian")
    assert "Застарілі дані" in uk and "None" not in uk


def test_wallet_callback_payloads_are_short_and_id_scoped() -> None:
    markups = (build_wallet_detail_keyboard(2**63 - 1), build_wallet_delete_confirmation(2**63 - 1))
    payloads = [button.callback_data for markup in markups for row in markup.inline_keyboard for button in row]
    assert all(payload is not None and len(payload.encode()) <= 64 for payload in payloads)
    assert all("0x" not in payload for payload in payloads)
