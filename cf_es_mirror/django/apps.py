from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

import cf_es_mirror
from cf_es_mirror import django as cf_es_mirror_module


class CfEsMirroAppConfig(AppConfig):
    name = "cf_es_mirror.django"
    label = "cf_es_mirror"
    verbose_name = _("Contentful-to-Elastic Mirror")

    def ready(self):
        from cf_es_mirror.config import Config
        from django.conf import settings
        Config.from_class(settings)
