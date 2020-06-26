from django.core.management.base import BaseCommand, CommandError
from cf_es_mirror.config import config
from cf_es_mirror.contentful import ContentType, Entry


class Command(BaseCommand):
    """
    Imports all documents to their specified content type(s).

    ---
    Please note that the storage/removal of documents depends on the CONTENTFUL_ACCESS_TOKEN's access.
    It is _imperative_ that you do not use this method with a PREVIEW token, when ENABLE_UNPUBLISHED is False!
    """

    def add_arguments(self, parser):
        parser.add_argument('--verbose', action='store_true', default=False)
        parser.add_argument('--token', default=None)

    def handle(self, verbose=False, token=None, *args, **kwargs):
        from contentful import DeletedAsset, DeletedEntry, Asset, Entry as CFEntry
        ASSET_TYPES = (DeletedAsset, Asset)
        ENTRY_TYPES = (CFEntry, DeletedEntry)

        if not config.contentful:
            raise CommandError("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                               "CONTENTFUL_ACCESS_TOKEN settingd.")

        if not token:
            if verbose: self.stdout.write("Performing initial sync.")
            sync = config.contentful.sync({'initial': True})
        else:
            if verbose: self.stdout.write("Continuing with existing sync.")
            sync = config.contentful.sync({'sync_token': token})
        while sync.items:
            if verbose: self.stdout.write(f"Sync batch items to process: {len(sync.items)}.")
            processed = 0
            for item in sync.items:
                if isinstance(item, ASSET_TYPES):
                    continue  # We don't index assets
                elif isinstance(item, ENTRY_TYPES):
                    processed += 1
                    obj = Entry(item.raw)
                    if not obj.valid_for_space():
                        continue  # We could echo something but that could get really spammy really quick.
                    if isinstance(item, DeletedEntry):
                        obj.unpublish()
                    else:
                        obj.publish()
            self.stdout.write(f"Processed {processed} items, next token: {sync.next_sync_token}.")
            sync = config.contentful.sync({'sync_token': sync.next_sync_token})
