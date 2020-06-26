from django.core.management.base import BaseCommand, CommandError
from cf_es_mirror.config import config
from cf_es_mirror.contentful import ContentType, Entry

class Command(BaseCommand):
    """
    Removes a content type from the search index.
    ---
    Please note that this also removes all content in this content type index.
    """
    
    def add_arguments(self, parser):
        parser.add_argument("--space", default=config.SPACE_ID)

    def handle(self, space=None, *args, **kwargs):
        if not config.contentful:
            raise CommandError("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                               "CONTENTFUL_ACCESS_TOKEN settingd.")
        space = space or config.SPACE_ID    
        obj = ContentType({"sys": {"id": content_type, "space": {"sys": {"id": space}}}})
        if not obj.valid_for_space():
            raise CommandError("Invalid for space.")
        else:
            obj.unpublish()
