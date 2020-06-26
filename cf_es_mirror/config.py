import os

from cf_es_mirror.util import to_bool, to_int, split_dict, split_list, cached_property
from cf_es_mirror.contentful import Client

from elasticsearch import Elasticsearch


class Config:
    # Elastic settings
    NUMBER_OF_SHARDS = 1
    NUMBER_OF_REPLICAS = None  # Set to something to force replicas being made.
    AUTO_EXPAND_REPLICAS = False
    INDEX_PREFIX = None
    CT_INDEX = "_content-types"  # STATIC
    REINDEX_INDEX = "_reindex"  # STATIC

    ELASTIC_URL = None
    ELASTIC_AUTH = None
    ELASTIC_SSL = False

    # Contentful settings
    API_HOST = None  # The contenful API URL.
    SPACE_ID = None  # The contentful space ID. The space ID to fall back to
    ACCESS_TOKEN = None  # The contentful access token. Only used to do calls to the `SPACE_ID` space
    SPACE_MAP = {}  # Maps <space id> to <name>. Useful to ensure indexes are created using easy-to-identify names, rather than a vague space ID.

    ACCEPTED_SPACE_IDS = [SPACE_ID]  # The space IDs we accept requests for.
    WEBHOOK_AUTH = {}  # A very crude authentication list.

    ALLOW_UNPUBLISHED = False  # Do we accept unpublished items. Set to True to also index items that are not published, Set to False (default) for 'production ready' behavior.

    # Language settings
    LANGUAGES = ["en"]
    DEFAULT_LANGUAGE = LANGUAGES[0]
    LANGUAGE_ANALYZERS = [
        'arabic',
        'armenian',
        'basque',
        'bengali',
        'brazilian',
        'bulgarian',
        'catalan',
        'cjk',
        'czech',
        'danish',
        'dutch',
        'english',
        'finnish',
        'french',
        'galician',
        'german',
        'greek',
        'hindi',
        'hungarian',
        'indonesian',
        'irish',
        'italian',
        'latvian',
        'lithuanian',
        'norwegian',
        'persian',
        'portuguese',
        'romanian',
        'russian',
        'sorani',
        'spanish',
        'swedish',
        'turkish',
        'thai',
    ]

    def index(self, name, space: str =None):
        prefix = self.INDEX_PREFIX or None
        space = space or self.SPACE_ID or None
        space = self.SPACE_MAP.get(space, space)
        return '-'.join([x for x in [prefix, space, name] if x is not None]).lower()

    def content_type_index(self, space: str =None):
        return self.index(self.CT_INDEX, space=space)

    def reindex_index(self, space: str =None):
        return self.index(self.REINDEX_INDEX, space=space)

    @cached_property
    def logger(self):
        from logging import getLogger
        return getLogger("contnetful-es-mirror")

    @cached_property
    def elastic(self) -> Elasticsearch:
        urls = self.ELASTIC_URL
        if urls:
            urls = list(urls.split(';'))
        kwargs = {
            'use_ssl': self.ELASTIC_SSL,
        }
        if self.ELASTIC_AUTH:
            kwargs['http_auth'] = self.ELASTIC_AUTH.split(':', 1)
        return Elasticsearch(urls, **kwargs)

    @cached_property
    def contentful(self):
        if self.SPACE_ID and self.ACCESS_TOKEN:
            return Client(api_url=self.API_HOST, space_id=self.SPACE_ID, access_token=self.ACCESS_TOKEN, content_type_cache=False, timeout_s=2)

    instance = None

    @classmethod
    def from_env(cls):
        """
        Retrieves all settings from `os.environ`
        """
        CAT_MAP = {
            "CONTENTFUL": ["CF", "CONTENFUL"],
            "ELASTIC": ["ES", "ELASTIC", "ELASTICSEARCH"],
        }

        def setting(name: str, category: str):
            for prefix in CAT_MAP.get(category, [""]):
                key = f"{prefix}_{name}" if prefix else name
                if key in os.environ:
                    return os.environ[key]
            raise KeyError(name)
        return cls.create_with_func(setting) 

    @classmethod
    def from_class(cls, config):
        """
        Retrieves all settings from `config`.
        """
        def setting(name: str, category: str):
            return getattr(config, f"{category}_{name}" if category else name)
        return cls.create_with_func(setting)

    @classmethod
    def create_with_func(cls, func):
        def _required(name, category, default=None):
            try:
                return func(name, category)
            except:
                raise Exception(f"Invalid configuration, option {category}/{name} is missing.")
        def _optional(name, category, default=None):
            try:
                return func(name, category)
            except:
                return default
        def get(name, category, default=None, conv=None, required=False, *args, **kwargs):
            val = (_required if required else _optional)(name, category, default)
            if conv:
                val = conv(val, default=default, *args, **kwargs)
            return val

        obj = cls()
        obj.NUMBER_OF_SHARDS = get("NUMBER_OF_SHARDS", "ELASTIC", cls.NUMBER_OF_SHARDS, conv=to_int)
        obj.NUMBER_OF_REPLICAS = get("NUMBER_OF_REPLICAS", "ELASTIC", cls.NUMBER_OF_REPLICAS, conv=to_int)
        obj.AUTO_EXPAND_REPLICAS = get("AUTO_EXPAND_REPLICAS", "ELASTIC", cls.AUTO_EXPAND_REPLICAS)
        obj.INDEX_PREFIX = get("INDEX_PREFIX", "ELASTIC", cls.INDEX_PREFIX)
        obj.ELASTIC_URL = get("URL", "ELASTIC", cls.ELASTIC_URL)
        obj.ELASTIC_AUTH = get("AUTH", "ELASTIC", cls.ELASTIC_AUTH)
        obj.ELASTIC_SSL = get("SSL" "ELASTIC", cls.ELASTIC_SSL)

        obj.SPACE_ID = get("SPACE_ID", "CONTENTFUL", required=True)
        obj.ACCESS_TOKEN = get("ACCESS_TOKEN", "CONTENTFUL", required=True)
        obj.API_HOST = get("HOST", "CONTENTFUL", "cdn.contentful.com")
        obj.SPACE_MAP = get("SPACE_MAP", "CONTENTFUL", cls.SPACE_MAP, conv=split_dict)
        obj.ACCEPTED_SPACE_IDS = get("ACCEPTED_SPACE_IDS", "CONTENTFUL", [obj.SPACE_ID], conv=split_list)
        obj.WEBHOOK_AUTH = get("WEBHOOK_AUTH", "CONTENTFUL", {}, conv=split_dict)

        obj.ALLOW_UNPUBLISHED = get("ALLOW_UNPUBLISHED", "", cls.ALLOW_UNPUBLISHED, conv=to_bool)
        obj.LANGUAGES = get("LANGUAGES", "", cls.LANGUAGES, conv=split_list)
        obj.DEFAULT_LANGUAGE = get("DEFAULT_LANGUAGE", "", obj.LANGUAGES[0])
        obj.LANGUAGE_ANALYZERS = get("LANGUAGE_ANALYZERS", "", cls.LANGUAGE_ANALYZERS)

        cls.instance = obj
        return obj


class ConfigHelper:
    def __getattribute__(self, key):
        if key.startswith("__"):
            return object.__getattribute__(self, key)
        if Config.instance is None:
            raise Exception(f"Access before configured: {key}")
        return getattr(Config.instance, key)

config = ConfigHelper()
