from django.core.management.base import BaseCommand, CommandError
from cf_es_mirror.config import config
from cf_es_mirror.contentful import ContentType, Entry

from .contentful_update import Command as UpdateCommand
from .contentful_import_all_documents import Command as ImportCommand


class Command(BaseCommand):
    """
    Imports the entire space if the database is empty
    ---
    Use the --force toggle to force this regardless of data already existing in the database
    """

    def add_arguments(self, parser):
        parser.add_argument('--verbose', action='store_true', default=False)
        parser.add_argument('--force', action='store_true', default=False)

    def handle(self, verbose=False, force=False, *args, **kwargs):
        if not config.contentful:
            raise CommandError("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                               "CONTENTFUL_ACCESS_TOKEN settingd.")
        doc = {
            "query": {
                "match_all": {}
            }
        }
        if not force:
            results = config.elastic.search(index=config.content_type_index(), body=doc)
            if len(results["hits"]["hits"]) > 0:
                self.stdout.write(f"Data already exists in database, skipping import. Use --force to force import on an existing database.")
                return
        self.stdout.write(f"Importing all content types.")
        UpdateCommand().handle(verbose=verbose)
        self.stdout.write(f"Importing all content. This might take a while...")
        ImportCommand().handle(verbose=verbose)
