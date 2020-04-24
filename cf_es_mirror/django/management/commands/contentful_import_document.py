from django.core.management.base import BaseCommand, CommandError
from cf_es_mirror.config import config
from cf_es_mirror.contentful import ContentType, Entry

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("docid", nargs="+")

    def handle(self, docid, *args, **kwargs):
        if not config.contentful:
            raise CommandError("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                               "CONTENTFUL_ACCESS_TOKEN settingd.")
        try:
            current_id = None
            for current_id in docid:
                item = config.contentful.entry(current_id, {'locale': '*'})
                obj = Entry(item.raw)
                if obj.valid_for_space():
                    obj.publish()
                else:
                    raise CommandError(f"Entry {current_id} is not valid for this space.")
        except:
            raise CommandError(f"Unable to find item with the content ID '{current_id}'.")
