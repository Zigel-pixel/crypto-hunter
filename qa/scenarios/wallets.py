from app.models.wallet_address import AddressFamily
from app.services.wallet_address_service import detect_wallet_address
from qa_bot.models import Scenario


async def addresses_check():
    evm = detect_wallet_address("  0x" + "a" * 40 + " ")
    tron = detect_wallet_address("TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj")
    ok = evm is not None and evm.family is AddressFamily.EVM and tron is not None and tron.family is AddressFamily.TRON
    return ok, "EVM and TRON detected without provider calls", "Network-free validators"


def scenarios():
    return (Scenario("wallets.addresses", "Wallet address families", "wallets", "Validate representative EVM and TRON public addresses.", "Typed EVM and TRON results", addresses_check, related_modules=("app/services/wallet_address_service.py",)),)
