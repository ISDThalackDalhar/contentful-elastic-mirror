import copy

from cf_es_mirror.contentful import ContentfulType
from cf_es_mirror.config import config
from cf_es_mirror.util import get_path, cached_property, merge

from cf_es_mirror.signals import *


class Entry(ContentfulType):
    def __init__(self, data):
        super().__init__(data)

        # Ensure validity of this Entry document:
        #  - It must have a sys.id
        #  - It must have a sys.contentType.sys.id
        #  - We must accept the space it is for (sys.space.sys.id)
        try:
            # self.content_type triggers KeyError if it is not present in the document
            # self.space triggers KeyError if it is not present in the document
            self.content_type_index = config.index(self.content_type, space=self.space)
            self.valid = self.valid_for_space() and self.document_id is not None
        except KeyError:
            # This is triggered when we cannot find an item in the document. Assume the document is invalid.
            self.valid = False

        if self.valid:
            # Don't hit elastic until we're convinced this document is valid to process.
            self.index_exists = config.elastic.indices.exists_alias(name=self.content_type_index)


    def store(self):
        # A request is made to store this document for indexing
        if not self.index_exists:
            # We can't index documents when we don't have the index mapping present, so log and return early.
            config.logger.warning("Attempting to index document of content type '%s.%s' (id: '%s'), but no index "
                                  "exists for this content type.", self.space, self.content_type, self.document_id)
            return

        body = copy.deepcopy(self.data)
        annotations = {}
        # Annotate our body via signal output
        for handler, data in annotate_entry_index.send(self.content_type, space=self.space, id=self.document_id, body=body):
            if isinstance(data, dict):
                merge(annotations, data)
        merge(body, annotations)

        # Signal we are about to index
        pre_entry_index.send(self.content_type, space=self.space, id=self.document_id, body=body)

        # Simply push it to elastic and we should be done.
        config.elastic.index(index=self.content_type_index, id=self.document_id, body=body, ignore=[400, 404], refresh=True)

        # Signal we are done indexing
        post_entry_index.send(self.content_type, space=self.space, id=self.document_id, body=body)


    def remove(self):
        # A request is made to remove this document from the index
        if not self.index_exists:
            # We can't remove an item from an index that does not exist. log and return early (this is not really an issue
            #  since a missing index doesn't have the specified document, but still, this is not an expected event).
            config.logger.warning("Attempting to remove document of content type '%s.%s' (id: '%s'), but no index "
                                  "exists for this content type.", self.space, self.content_type, self.document_id)
            return

        # Signal we are about to remove a document
        pre_entry_remove.send(self.content_type, space=self.space, id=self.document_id)

        # Tell elastic to remove the document, ignore if the document is not indexed to begin with.
        config.elastic.delete(index=self.content_type_index, id=self.document_id, ignore=[400, 404])

        # Signal we are done removing
        post_entry_remove.send(self.content_type, space=self.space, id=self.document_id)


    # Contentful has a events it calls webhooks for:
    # - create: The entry is created
    # - save: There entry is being saved
    # - auto_save: The auto-save of the editor is being triggered
    # - archive: The entry is being archived
    # - unarchive: The entry is being unarchived
    # - publish: The entry is being published
    # - unpublish: The entry is being unpubslished
    # - delete: The entry is being deleted

    def create(self):
        # A noop since we don't have any data to index at this point.
        pass

    def save(self):
        # In all cases this would save a draft version of this document,
        #  as such, we can only store this if we save unpublished content
        if self.store_unpublished:
            self.store()

    def auto_save(self):
        # Same as save()
        if self.store_unpublished:
            self.store()

    def archive(self):
        # When archiving the item is guaranteed to be unavailable.
        #  As such, we remove it always
        self.remove()

    def unarchive(self):
        # When unarchiving, the item returns as an unpublished document. Treat it as such.
        if self.store_unpublished:
            self.store()

    def publish(self):
        # Speaks for itself, really.
        self.store()

    def unpublish(self):
        # If we store unpublished, we can keep it, otherwise, we remove it from the index.
        if not self.store_unpublished:
            self.remove()

    def delete(self):
        # The item is removed completely, so we remove it as well.
        self.remove()

    ACTIONS = [
        'archive',
        'auto_save',
        'create',
        'delete',
        'publish',
        'save',
        'unarchive',
        'unpublish',
    ]

