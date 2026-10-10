import importlib
import os
import unittest
from unittest.mock import patch


with patch.dict(os.environ, {
    "BOT_TOKEN": "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
    "OPENWEATHER_KEY": "test-placeholder",
    "NEWSAPI_KEY": "test-placeholder",
    "ADMINS": "1",
}):
    import config
    importlib.reload(config)
    import bot


class BotHelperTests(unittest.TestCase):
    def test_every_display_city_has_an_api_mapping(self):
        self.assertEqual(set(bot.CITIES_SHOW), set(bot.CITY_MAP))

    def test_non_english_city_names_are_mapped(self):
        self.assertEqual(bot.resolve_city(bot.CITIES_SHOW[5]), "Fergana")
        self.assertEqual(bot.resolve_city(bot.CITIES_SHOW[12]), "Nukus")


if __name__ == "__main__":
    unittest.main()
