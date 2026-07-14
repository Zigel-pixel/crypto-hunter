from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.models.consultant import ConsultantIntent
from app.services.consultant_intent_service import classify_query
from app.services.consultant_service import answer_consultant_question
from app.handlers.consultant import answer_question


class ConsultantIntentTests(unittest.TestCase):
    def test_stablecoin_question(self) -> None:
        result = classify_query("Що ти скажеш про стейблкоїни?", "Ukrainian")
        self.assertEqual(result.intent, ConsultantIntent.STABLECOIN)

    def test_asset_comparison(self) -> None:
        result = classify_query("Compare ETH versus SOL")
        self.assertEqual(result.intent, ConsultantIntent.COMPARISON)
        self.assertEqual(result.assets, ("ETH", "SOL"))

    def test_trading_decision(self) -> None:
        self.assertEqual(classify_query("Should I buy BTC?").intent, ConsultantIntent.TRADING_DECISION)

    def test_defi(self) -> None:
        self.assertEqual(classify_query("What is DeFi?").intent, ConsultantIntent.DEFI)


class ConsultantResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_stablecoin_answer_is_relevant_without_btc_template(self) -> None:
        text = await answer_consultant_question("Що ти скажеш про стейблкоїни?", "Ukrainian")
        self.assertIn("USDT", text)
        self.assertIn("USDC", text)
        self.assertIn("DAI", text)
        self.assertNotIn("BTC зараз", text)
        self.assertNotIn("не персональна фінансова рекомендація", text)

    async def test_english_stablecoin_answer_covers_core_risks(self) -> None:
        text = await answer_consultant_question("What do you think about stablecoins?", "English")
        for term in ("USDT", "USDC", "DAI", "issuer", "reserve", "depegging", "liquidity", "yield"):
            self.assertIn(term, text)

    async def test_comparison_and_buy_questions_use_specific_paths(self) -> None:
        snapshots = {"ethereum": unittest.mock.Mock(price=3000, change_24h=1, symbol="eth"), "solana": unittest.mock.Mock(price=150, change_24h=-1, symbol="sol"), "bitcoin": unittest.mock.Mock(price=60000, change_24h=3, symbol="btc")}
        with patch("app.services.consultant_service.fetch_market_snapshots", AsyncMock(return_value=("now", snapshots))):
            comparison = await answer_consultant_question("ETH versus SOL", "English")
            buy = await answer_consultant_question("Should I buy BTC?", "English")
        self.assertIn("ETH", comparison); self.assertIn("SOL", comparison)
        self.assertIn("Signal:", buy); self.assertNotIn("Current market", buy)

    async def test_technical_question_has_no_forced_signal(self) -> None:
        text = await answer_consultant_question("What is DeFi?", "English")
        self.assertNotIn("Signal:", text)

    async def test_production_handler_routes_to_topic_aware_pipeline(self) -> None:
        message = SimpleNamespace(text="Що ти скажеш про стейблкоїни?", from_user=SimpleNamespace(id=7), answer=AsyncMock())
        state = SimpleNamespace(clear=AsyncMock())
        with patch("app.handlers.consultant.get_setting", AsyncMock(return_value="Ukrainian")), patch(
            "app.handlers.consultant.answer_consultant_question", AsyncMock(return_value="USDT USDC DAI issuer reserve depeg")
        ) as pipeline:
            await answer_question(message, state)
        pipeline.assert_awaited_once_with(message.text, "Ukrainian")
        self.assertIn("USDT", message.answer.await_args.args[0])

    async def test_concepts_do_not_return_generic_btc_dump(self) -> None:
        for question, language in (("What are stablecoins?", "English"), ("What is DeFi?", "English"), ("Поясни смартконтракти", "Ukrainian")):
            text = await answer_consultant_question(question, language)
            self.assertNotIn("Current market", text)
            self.assertNotIn("BTC:", text)
