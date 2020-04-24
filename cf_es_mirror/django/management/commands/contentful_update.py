from django.core.management.base import BaseCommand, CommandError
from cf_es_mirror.config import config
from cf_es_mirror.contentful import ContentType, Entry

class Command(BaseCommand):
    """
    Fetches all content types from the back-end, updating where needed
    ---
    Specify --force to force reindexing of all affected content types.
    """

    def add_arguments(self, parser):
        parser.add_argument('--verbose', action='store_true', default=False)
        parser.add_argument('--dry-run', action='store_true', default=False)
        parser.add_argument('--force', action='store_true', default=False)

    def handle(self, verbose=False, dry_run=False, force=False):
        if not config.contentful:
            raise CommandError("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                               "CONTENTFUL_ACCESS_TOKEN settingd.")
        for ct in config.contentful.content_types():
            if verbose: self.stdout.write(f"Processing content type: '{ct.id}'")
            if not dry_run:
                obj = ContentType(ct.raw)
                if not obj.valid_for_space():
                    if verbose: self.stderr.write("Invalid for space, skipping")
                else:
                    obj.reindex_if_needed(force=force)
