import importlib
import os
import unittest
from unittest.mock import patch


class ConfigTests(unittest.TestCase):
    def test_admin_ids_are_parsed(self):
        with patch.dict(os.environ, {"ADMINS": "12, 34"}):
            import config
            importlib.reload(config)
            self.assertEqual(config.ADMINS, [12, 34])

    def test_validate_config_reports_missing_names_only(self):
        with patch.dict(os.environ, {"BOT_TOKEN": "", "OPENWEATHER_KEY": "", "NEWSAPI_KEY": ""}, clear=False):
            import config
            importlib.reload(config)
            with self.assertRaisesRegex(RuntimeError, "BOT_TOKEN.*OPENWEATHER_KEY.*NEWSAPI_KEY"):
                config.validate_config()


if __name__ == "__main__":
    unittest.main()
