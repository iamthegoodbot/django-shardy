from django.db import models

from .querysets import (
    ShardPerTenantQuerySet,
    ShardRawPerTenantQuerySet
)


class ShardedPerTenantManager(models.Manager):

    def get_queryset(self):
        return ShardPerTenantQuerySet(model=self.model, using=self._db)

    def raw(self, raw_query, model=None, query=None, params=None,
            translations=None, using=None):
        return ShardRawPerTenantQuerySet(
            raw_query=raw_query, model=self.model,
            params=params, using=using
        )
