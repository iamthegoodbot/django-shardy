from django.test import TestCase

from shardy.querysets import (
    ShardPerTenantQuerySet,
    ShardRawPerTenantQuerySet
)
from .models import TShardedModel


class ShardedPerTenantManagerTestCase(TestCase):

    def test_get_queryset(self):
        qs = TShardedModel.objects.get_queryset()
        self.assertIsInstance(qs, ShardPerTenantQuerySet)

    def test_raw(self):
        qs = TShardedModel.objects.raw('SELECT 1;')
        self.assertIsInstance(qs, ShardRawPerTenantQuerySet)
