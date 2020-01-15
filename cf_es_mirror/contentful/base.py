from cf_es_mirror.util import get_path, cached_property
from cf_es_mirror.config import config


class ContentfulType:
    def __init__(self, data):
        self.data = data

    ACTIONS = []

    @property
    def store_unpublished(self):
        return config.ALLOW_UNPUBLISHED

    @cached_property
    def space(self):
        return get_path(self.data, "sys", "space", "sys", "id", default=config.SPACE_ID)

    @cached_property
    def document_id(self):
        return get_path(self.data, "sys", "id", default=KeyError("sys.id"))
    
    @cached_property
    def content_type(self):
        return get_path(self.data, "sys", "contentType", "sys", "id", default=KeyError("sys.contentType.sys.id"))
    
    def valid_for_space(self):
        if '*' in config.ACCEPTED_SPACE_IDS:
            return True
        return self.space in config.ACCEPTED_SPACE_IDS

    @classmethod
    def get_type(cls, name):
        from cf_es_mirror.contentful import ContentType, Entry
        return {
            "ContentType": ContentType,
            "Entry": Entry,
        }.get(name, None)
