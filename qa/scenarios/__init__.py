from qa.scenarios.alerts import scenarios as alert_scenarios
from qa.scenarios.ai_consultant import scenarios as ai_scenarios
from qa.scenarios.favorites import scenarios as favorite_scenarios
from qa.scenarios.live import scenarios as live_scenarios
from qa.scenarios.localization import scenarios as localization_scenarios
from qa.scenarios.smoke import scenarios as smoke_scenarios
from qa.scenarios.wallets import scenarios as wallet_scenarios


def all_scenarios():
    return (*smoke_scenarios(), *localization_scenarios(), *live_scenarios(), *favorite_scenarios(), *alert_scenarios(), *ai_scenarios(), *wallet_scenarios())
