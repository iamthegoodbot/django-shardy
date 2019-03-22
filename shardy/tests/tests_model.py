from django.test import TestCase
from django.test.utils import override_settings

from app.models import AppTShardedModel
from shardy.db_routers import ShardedPerTenantRouter
from shardy.managers import ShardedPerTenantManager
from shardy.models import (
    SharedFieldIsUndefined,
)
from .models import (
    TShardedModel,
    TShardedUndefinedModel
)

PID = 1


class MainTest(TestCase):

    def setUp(self):
        ShardedPerTenantRouter._lookup_cache = {}

    def test_objects(self):
        self.assertIsInstance(TShardedModel.objects, ShardedPerTenantManager)

    def test_sharded_value(self):
        obj = TShardedModel(partner_id=PID)
        self.assertEqual(obj.sharded_value, PID)

    def test_corect_workflow(self):
        obj = TShardedModel(partner_id=PID)
        self.assertEqual(obj.partner_id, PID)

    def test_undefined_sharded_field(self):
        with self.assertRaises(SharedFieldIsUndefined):
            TShardedUndefinedModel(partner_id=PID)

    @override_settings(
        DATABASE_ROUTERS=['shardy.db_routers.ShardedPerTenantRouter'],
        DEFAULT_DB_GROUP='default',
        DATABASE_CONFIG={'routing': {}},
        DATABASES={
            'default__{}'.format(PID): {},
        }
    )
    def test_refresh_from_db(self):
        from django.db import connections
        import pudb; pudb.set_trace()
        obj = AppTShardedModel.objects.create(partner_id=PID, name='Test')
        obj = AppTShardedModel.objects.get(pk=obj.pk, partner_id=obj.partner_id)

        obj.refresh_from_db()

        self.assertEqual(obj.name, 'Test')


@override_settings(
    DATABASE_ROUTERS=[
        'shardy.db_routers.ShardedPerTenantRouter'
    ],
    DATABASE_CONFIG={
        'routing': {
            'shardy.tshardedmodel': {
                'write': 'test1',
                'read': 'test1',
            }
        }
    },
    DATABASES={
        'test1__{}'.format(PID): {},
    }
)
class SharedPerTenantModelDbAliasesTestCase(TestCase):

    def setUp(self):
        ShardedPerTenantRouter._lookup_cache = {}

    def test_get_db_alias_default(self):
        alias = TShardedModel.get_db_alias(PID)
        self.assertEqual(
            alias,
            'test1__{}'.format(PID)
        )

    def test_get_db_alias_replica(self):
        alias = TShardedModel.get_db_alias(PID, using='replica')
        self.assertEqual(
            alias,
            'test1__{}__replica'.format(PID)
        )
