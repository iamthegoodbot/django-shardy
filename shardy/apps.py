from django.apps import AppConfig
from django.conf import settings


class ShardyConfig(AppConfig):
    name = 'shardy'

    @property
    def settings(self):
        class Config:
            DEFAULT_DB_GROUP = getattr(settings, 'DEFAULT_DB_GROUP', 'default')
            SHARD_SEPARATOR = getattr(settings, 'SHARD_SEPARATOR', '__')
            DATABASE_CONFIG = getattr(settings, 'DATABASE_CONFIG', {})
            DATABASES = getattr(settings, 'DATABASES')

        return Config()
