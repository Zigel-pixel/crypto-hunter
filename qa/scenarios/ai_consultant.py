from app.models.consultant import ConsultantIntent
from app.services.consultant_intent_service import classify_query
from app.services.consultant_service import answer_consultant_question
from qa_bot.models import Scenario


async def intent_check():
    stable = classify_query("Що ти скажеш про стейблкоїни?", "Ukrainian")
    comparison = classify_query("Compare ETH versus SOL", "English")
    return stable.intent is ConsultantIntent.STABLECOIN and comparison.intent is ConsultantIntent.COMPARISON, f"{stable.intent}, {comparison.intent}", "No external AI provider used"


async def fallback_check():
    text = await answer_consultant_question("What is DeFi?", "English")
    return "DeFi" in text and "Signal:" not in text, text, "Topic-aware free fallback"


def scenarios():
    return (
        Scenario("ai.intent", "Consultant intent routing", "ai", "Classify stablecoin and comparison questions.", "Correct topic-specific intents", intent_check, related_modules=("app/services/consultant_intent_service.py",)),
        Scenario("ai.fallback", "Topic-aware AI fallback", "ai", "Answer a technical DeFi question without a trading signal.", "Relevant educational response without forced signal", fallback_check, related_modules=("app/services/consultant_service.py",)),
    )
