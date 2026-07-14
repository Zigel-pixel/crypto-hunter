from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.models.consultant import ConsultantIntent
from app.services.consultant_intent_service import classify_query
from app.services.consultant_service import answer_consultant_question


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

    async def test_technical_question_has_no_forced_signal(self) -> None:
        text = await answer_consultant_question("What is DeFi?", "English")
        self.assertNotIn("Signal:", text)
