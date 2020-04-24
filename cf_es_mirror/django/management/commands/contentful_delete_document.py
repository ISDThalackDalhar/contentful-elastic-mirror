import sys

from django.core.management.base import BaseCommand, CommandError
from cf_es_mirror.config import config
from cf_es_mirror.contentful import ContentType, Entry

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("content_type", nargs="1")
        parser.add_argument("docid", nargs="+")

    def handle(self, docid, *args, **kwargs):
        if not config.contentful:
            raise CommandError("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                               "CONTENTFUL_ACCESS_TOKEN settingd.")
        for current_id in docid:
            data = {
                'sys': {
                    'contentType': {'sys': {'id': content_type}},
                    'id': docid,
                },
            }
            obj = Entry(data)
            if obj.valid_for_space():
                obj.delete()
            else:
                self.stderr.write("Entry is not valid for space")
                sys.exit(1)
