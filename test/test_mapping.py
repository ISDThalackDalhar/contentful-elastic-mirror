import babel

from .base import BaseTestCase, config

from cf_es_mirror.contentful import mapping
from cf_es_mirror.contentful.content_type import _get_mapping_type as get_mapping_type, _per_language_field as per_language_field, ENGLISH

class ValidationTestCase(BaseTestCase):
    def test_base_mapping_types(self):
        self.assertEqual(get_mapping_type({"type": ""}), mapping.DISABLED)
        self.assertEqual(get_mapping_type({"type": "Text"}), mapping.TEXT)
        self.assertEqual(get_mapping_type({"type": "Integer"}), mapping.INT)

    def test_text_field(self):
        mapped = per_language_field({"type": "Text"})
        self.assertTrue(config.DEFAULT_LANGUAGE in mapped["properties"])
        lang = mapped["properties"][config.DEFAULT_LANGUAGE]
        self.assertEqual(lang["type"], "text")
        self.assertTrue("analyzer" in lang)
        self.assertTrue("trigrams" in lang["fields"])
        self.assertEqual(lang["analyzer"], babel.Locale.parse(config.DEFAULT_LANGUAGE, sep='-').get_language_name(ENGLISH).lower())
        self.assertTrue(lang["analyzer"] in config.LANGUAGE_ANALYZERS)
