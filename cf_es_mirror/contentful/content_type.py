import copy
import hashlib
import json

import babel

from cf_es_mirror.contentful import ContentfulType, mapping
from cf_es_mirror.config import config
from cf_es_mirror.util import cached_property, merge

from cf_es_mirror.signals import *


ENGLISH = babel.Locale.parse('en')

DEFAULT_SETTINGS = {
    "analysis": {
        "tokenizer": {
            "trigrams": {
                "type": "ngram",
                "min_gram": 3,
                "max_gram": 3,
                "token_chars": [
                    "letter", "digit",
                ]
            }
        },
        "analyzer": {
            "trigrams": {
                "tokenizer": "trigrams",
                "char_filter": [
                    "html_strip",
                ],
                "filter": [
                    "lowercase",
                    "asciifolding",
                ],
            },
        },
    }
}
EXTRA_ANALYZERS_FIELDS = {
    "trigrams": {
        "type": "text",
        "analyzer": "trigrams",
    }
}
DISPLAY_FIELD_EXTRA_FIELDS = {
    "keyword": {
        "type": "keyword",
    }
}


def get_language_analyzer(lang_code: str, mapping_type: dict, displayField=False) -> dict:
    """
    To provide better searchability, we provide a per-language analyzer for text fields.

    :param lang_code: The language code (as specified by Contentful) that this field is for.
    :param mapping_type: The mapping type we will be applying to this field.
    :returns: The applied analyzers on this mapping, if applicable.
    """
    if not mapping_type.get("type", None) == "text":
        # We only specify analyzers for text fields.
        return mapping_type
    try:
        loc = babel.Locale.parse(lang_code, sep='-')
    except ValueError:
        # Babel doesn't recognize this locale, so we can't proceed.
        return mapping_type
    lang = loc.get_language_name(ENGLISH).lower()
    fields = {}
    extra = {}
    if displayField:
        fields.update(DISPLAY_FIELD_EXTRA_FIELDS)
    if lang in config.LANGUAGE_ANALYZERS:
        # Apply the following:
        # 1. Our analyzer. Elastic has a list of supported analyzers (specified in config.LANGUAGE_ANALYZERS)
        #    for full-text searching
        # 2. Our extra analzyers. By default we add a trigrams field analyzer
        # 3. Term vector information, for faster searching and finding related documents
        fields.update(EXTRA_ANALYZERS_FIELDS)
        extra.update({
            "term_vector": "with_positions_offsets",
            "analyzer": lang,
        })
    return {**mapping_type, "fields": fields, **extra}


def get_mapping_type(field):
    """
    Fetch the mapping type for this field type

    Defaults to DISABLED to avoid indexing unknown fields (not NOT_INDEXED as we might want to be able to search on it)
    """
    if field["type"] in mapping.FIELDS:
        return mapping.FIELDS[field["type"]]
    if field["type"] in ("Array",):
        return get_mapping_type(field["items"])
    return mapping.DISABLED


def per_language_field(field, displayField=False):
    mapped = get_mapping_type(field)
    return {
        "properties": {
            lc: get_language_analyzer(lc, mapped, displayField=displayField)
            for lc in (config.LANGUAGES if field.get("localized", False) else [config.DEFAULT_LANGUAGE])
        }
    }


class ContentType(ContentfulType):
    def __init__(self, data):
        super().__init__(data)

        self.content_type_index = config.content_type_index(space=self.space)
        self.reindex_index = config.reindex_index(space=self.space)

        self.index_alias = config.index(self.document_id, space=self.space)
        self.index_wildcard = f"{self.index_alias}-*"

    def check_indices(self):
        #
        # We require 2 indices to always exist, regardless of the amount of content indices.
        #  These indices allow us to perform various tasks, as well as keeping track of some information.
        #
        if not config.elastic.indices.exists(index=self.reindex_index):
            # Create the reindex index. This index only keeps track of content types being reindexed, as a crude locking mechanism.
            config.elastic.indices.create(index=self.reindex_index, body=self.get_settings(),
                                          wait_for_active_shards=1)
        if not config.elastic.indices.exists(index=self.content_type_index):
            # Create the content type index. This index keeps track of all content types and their layout.
            config.elastic.indices.create(index=self.content_type_index, body=self.get_settings(),
                                          wait_for_active_shards=1)
            config.elastic.indices.put_mapping(mapping.TYPES_MAPPING, index=self.content_type_index)

        # Next up we check if our index alias exists
        self.index_alias_exists = config.elastic.indices.exists_alias(name=self.index_alias)
        self.existing_indices = config.elastic.indices.get_alias(index=self.index_wildcard, name=self.index_alias, expand_wildcards='open',
                                                                 ignore_unavailable=True, ignore=[404])
        if 'error' in self.existing_indices and self.existing_indices.get('status', 200) == 404:
            self.existing_indices = {}
        
        self.existing_content_type = {}
        if config.elastic.exists(index=self.content_type_index, id=self.document_id):
            self.existing_content_type = config.elastic.get_source(index=self.content_type_index, id=self.document_id)

    def get_settings(self):
        """
        Returns a new instance of the default settings
        """
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        settings.update({
            "number_of_shards": config.NUMBER_OF_SHARDS,
            "number_of_replicas": config.NUMBER_OF_REPLICAS if config.NUMBER_OF_REPLICAS is not None else 0,
            "auto_expand_replicas": config.AUTO_EXPAND_REPLICAS if config.AUTO_EXPAND_REPLICAS else False,
        })
        return {
            "settings": settings,
        }

    def build_mapping(self):
        displayField = self.data.get("displayField", None)
        return {
            "_source": {
                "enabled": True,
                "excludes": [
                    "sys.*By",  # sys.createdBy, sys.updatedBy
                    "sys.type",
                    "sys.space",
                    "sys.contentType",
                    "sys.environment",
                ],
            },
            "properties": {
                "sys": mapping.SYS,
                "fields": {
                    "properties": {
                        field['id']: per_language_field(field, field['id'] == displayField)
                        for field in sorted(self.data['fields'], key=lambda x: x['id'])
                    }
                }
            }
        }

    def reindex_if_needed(self, force=False, **kwargs):
        """
        (re)creates a search index for this content type.

        This process takes the following steps:

        1. Build a new index
        2. Apply our generated mapping to said index
        3. Update the content type alias to this new index
        4. Re-index the existing content type data into this new index
        """
        self.check_indices()

        # Sanity check
        if self.index_alias_exists and not self.existing_indices:
            # This should never happen, as <space>-<type> should always be mapped to <space>-<type>-<id>,
            #  but just in case
            config.logger.error(f"An alias has been found for the '{self.space}.{self.document_id}' content type, but not index is connected.")
            return

        new_fields = self.data.get("fields", {"_non_existent_data": "new"})  # Defaulting to a specific value so it does not match any existing data.
        existing_fields = self.existing_content_type.get("fields", {"_non_existent_data": "current"})  # Defaulting to a specific value so it does not match any new data.

        # Test if we actually have to do something.
        if new_fields == existing_fields and (self.index_alias_exists or self.existing_indices) and not force:
            # If we don't notice any changes to the field layout, we do not need to do any reindexing.
            config.logger.info(f"Content type '{self.space}.{self.document_id}'' has not changed, not re-indexing.")
            return

        suffix = hashlib.sha1(json.dumps(new_fields, sort_keys=True).encode('ascii', 'ignore')).hexdigest()[:8]  # This should be sufficient for a uniqueness check
        new_index_name = base_new_index_name = f"{self.index_alias}-{suffix}"
        # Ensure that if we force a reindex we create a new unique index name.
        i = 1
        while config.elastic.indices.exists(index=new_index_name):
            i += 1
            new_index_name = f"{base_new_index_name}-{i}"

        # Signal we are about to create an index
        pre_index_create.send(self.document_id, space=self.space, index=new_index_name, **kwargs)

        # 1. Build a new index
        config.logger.info(f"Building a new index: '{self.space}.{self.document_id}' -> '{new_index_name}'")
        config.elastic.indices.create(index=new_index_name, body=self.get_settings(), wait_for_active_shards=1)
        config.elastic.index(index=self.content_type_index, id=self.document_id, body=self.data)

        mapping = None
        # 2. Apply our generated mapping to said index
        try:
            mapping = self.build_mapping()
            annotations = {}
            # Annotate our mapping via signal
            for handler, data in annotate_index_create.send(self.document_id, space=self.space, mapping=mapping, data=self.data):
                if isinstance(data, dict):
                    merge(annotations, data)
            merge(mapping, annotations)
            # Build our mapping. If this process fails we have to abort early.
            config.elastic.indices.put_mapping(mapping, index=new_index_name)
        except:
            config.logger.exception(f"An error happened while creating the mapping for the new index '{new_index_name}' for '{self.space}.{self.document_id}'")
            config.logger.error("Cleaning up the index we created")
            config.elastic.indices.close(index=new_index_name)
            config.elastic.indices.delete(index=new_index_name)
            config.logger.error("Aborting creation")
            config.logger.debug("Mapping data: ")
            config.logger.debug(mapping)
            return

        # 3. Update the content type alias to this new index
        if not self.index_alias_exists:
            config.logger.debug(f"Creating alias '{self.index_alias}' for '{new_index_name}'")
            config.elastic.indices.put_alias(index=new_index_name, name=self.index_alias)
        else:
            config.logger.debug(f"Updating alias '{self.index_alias}' for '{new_index_name}'")
            # Add our new index as an alias, and at the same time, iterate over all existing indices for our alias and remove them.
            # This should leave us with just one target for the alias; our newly created index.
            # This also means that at this point, the new index becomes primary.
            config.elastic.indices.update_aliases({
                "actions": [
                    {"add": {"index": new_index_name, "alias": self.index_alias}},
                    *[
                        {"remove": {"index": name, "alias": self.index_alias}}
                        for name in self.existing_indices.keys()
                    ]
                ]
            })

        old_suffix = hashlib.sha1(json.dumps(existing_fields, sort_keys=True).encode('ascii', 'ignore')).hexdigest()[:8]
        old_index_name = f"{self.index_alias}-{old_suffix}"
        if self.index_alias_exists and self.existing_indices:
            old_index_name = list(self.existing_indices.keys())[0]

        # Quickly check if an existing reindex might already be happening, in this case, we wait.
        while config.elastic.exists(index=self.reindex_index, id=self.document_id):
                config.logger.info("A re-index is already underway, checking for completion status.")
                # Grab the task data
                data = config.elastic.get_source(index=self.reindex_index, id=self.document_id)
                # Get the task, tell elastic we'll wait until it's done.
                config.elastic.tasks.get(task_id=data['task'], wait_for_completion=True, ignore=[400, 404])
                # Remove the task item, since we're done.
                config.elastic.delete(index=self.reindex_index, id=self.document_id, ignore=[400, 404])

        # 4. Re-index the existing content type data into this new index
        if old_index_name in self.existing_indices:
            config.logger.info(f"Re-indexing '{old_index_name}' to '{new_index_name}'")
            # Start the reindex, don't wait (yet) so we get the task information
            data = config.elastic.reindex({"source": {"index": old_index_name}, "dest": {"index": new_index_name}},
                                          refresh=True, wait_for_completion=False)
            # Store our task data in the reindex index, so we effective lock it
            config.elastic.create(index=self.reindex_index, id=self.document_id, body=data)
            # Now we wait until it's done
            config.elastic.tasks.get(task_id=data['task'], wait_for_completion=True, ignore=[400, 404])
            # Remove the task item, since we're done.
            config.elastic.delete(index=self.reindex_index, id=self.document_id, ignore=[400, 404])
            config.logger.info(f"Removing old index: '{old_index_name}'")
            config.elastic.indices.close(index=old_index_name)
            config.elastic.indices.delete(index=old_index_name)
        elif self.existing_indices:
            config.logger.warning(f"We expected index '{old_index_name}' to exist, but it was not present in the existing list of indices.")

        # Signal we are done creating the index
        post_index_create.send(self.document_id, space=self.space, index=new_index_name, **kwargs)


    def remove_index(self):
        """
        Remove this content type from elastic
        """
        self.check_indices()

        pre_index_remove.send(self.document_id)

        # Remove our content type data from the content types index
        if self.existing_content_type:
            config.elastic.delete(index=self.content_type_index, id=self.document_id, ignore=[400, 404])

        # Sanity check first
        if self.index_alias_exists and not self.existing_indices:
            config.logger.error(f"An alias has been found for the '{self.space}.{self.document_id}' content type, but not index is connected.")
            return

        # Remove our content type alias
        if self.index_alias_exists:
            config.logger.info(f"Removing alias: '{self.index_alias}'")
            config.elastic.indices.delete_alias(index="_all", name=self.index_alias, ignore=[400, 404])
        # Close all our indices first (this should be only one)
        for name in self.existing_indices.keys():
            config.logger.info(f"Closing index: '{name}'")
            config.elastic.indices.close(index=name, ignore=[400, 404])
        for name in self.existing_indices.keys():
            config.logger.info(f"Deleting index: '{name}'")
            config.elastic.indices.delete(index=name, ignore=[400, 404])

        post_index_remove.send(self.document_id)

    def create(self):
        # A noop, a create is followed by a `save`/`publish`, and a create won't have any data, so there's no use in creating an empty index.
        pass

    def delete(self):
        # A noop, a delete has been preceeded by an `unpublish`, which already removes the index. So we don't have to do anything.
        pass

    def save(self):
        # A noop, a save indicates a change is made, but it does not mean that that change is live, this happens during a `publish`
        pass

    def publish(self):
        self.reindex_if_needed()

    def unpublish(self):
        self.remove_index()

    ACTIONS = [
        'create',
        'delete',
        'publish',
        'save',
        'unpublish',
    ]
