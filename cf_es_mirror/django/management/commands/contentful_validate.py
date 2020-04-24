import sys
from django.core.management.base import BaseCommand, CommandError
from cf_es_mirror.config import config
from cf_es_mirror.contentful import ContentType, Entry

class Command(BaseCommand):
    """
    Validate our configuration
    """

    def handle(self, *args, **options):
        if not config.contentful:
            raise CommandError("Contentful is not configured, please specify the CONTENTFUL_SPACE_ID and "
                               "CONTENTFUL_ACCESS_TOKEN settingd.")
        space = config.contentful.space()

        codes = [x.code for x in space.locales]
        primary = [x.code for x in space.locales if x.default]
        primary = primary[0] if primary else (codes[0] if codes else 'N/A')

        self.stdout.write("Current config:")
        self.stdout.write(" CONTENTFUL_LANGUAGES=%s" % ','.join(sorted(config.LANGUAGES)))
        self.stdout.write(" CONTENTFUL_DEFAULT_LANGUAGE=%s" % config.DEFAULT_LANGUAGE)
        self.stdout.write("Discovered:")
        self.stdout.write(" CONTENTFUL_LANGUAGES=%s" % ','.join(sorted(codes)))
        self.stdout.write(" CONTENTFUL_DEFAULT_LANG=%s" % primary)

        if not set(config.LANGUAGES) == set(codes):
            self.stderr.write("Please update CONTENTFUL_LANGUAGES to match")
            sys.exit(1)
        if not config.DEFAULT_LANGUAGE == primary:
            self.stderr.write("Please update CONTENTFUL_DEFAULT_LANGUAGE to match")
            sys.exit(1)
        self.stdout.write("Configuration matches")
