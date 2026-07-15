import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aiosqlite

from app.services import settings_service
from app.services.settings_service import get_setting, resolve_user_language, upsert_setting
from app.utils.i18n import canonical_language, normalize_language


class LanguageResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_canonical_storage_and_legacy_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "settings.db")
            async with aiosqlite.connect(path) as db:
                await db.execute("CREATE TABLE settings (telegram_id INTEGER, category TEXT, value TEXT, PRIMARY KEY (telegram_id, category))")
                await db.commit()
            with patch.object(settings_service, "DB_NAME", path):
                await upsert_setting(1, "language", "Українська")
                self.assertEqual(await resolve_user_language(1), "Ukrainian")
                async with aiosqlite.connect(path) as db:
                    stored = (await (await db.execute("SELECT value FROM settings")).fetchone())[0]
                self.assertEqual(stored, "uk")
                await upsert_setting(2, "language", "ENGLISH")
                self.assertEqual(await get_setting(2, "language"), "English")

    def test_aliases_are_deterministic(self) -> None:
        for value in ("uk", "ua", "Ukrainian", "українська"):
            self.assertEqual(normalize_language(value), "Ukrainian")
            self.assertEqual(canonical_language(value), "uk")

    def test_authoritative_paths_do_not_read_raw_language_setting(self) -> None:
        for path in (
            "app/handlers/common.py", "app/handlers/favorites.py",
            "app/handlers/news.py", "app/handlers/settings.py",
        ):
            source = Path(path).read_text(encoding="utf-8")
            self.assertNotIn('get_setting(message.from_user.id, "language")', source, path)
            self.assertNotIn('get_setting(callback.from_user.id, "language")', source, path)
