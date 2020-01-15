import unittest

from cf_es_mirror.config import Config, config


class BaseTestCase(unittest.TestCase):
    EXTRA_SETTINGS = {}
    @classmethod
    def setUpClass(cls):
        Config.from_env()
        for k, v in cls.EXTRA_SETTINGS.items():
            setattr(Config.instance, k, v)
