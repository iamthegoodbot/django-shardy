# coding=utf-8
from django.test import TestCase
from django.test.utils import override_settings

from app.models import AppTShardedModel as TShardedModel
from shardy.db_routers import ShardedPerTenantRouter
from shardy.querysets import ShardPerTenantQuerySetBulkCreate


PID = 1


@override_settings(
    DATABASE_ROUTERS=['shardy.db_routers.ShardedPerTenantRouter'],
    DATABASE_CONFIG={
        'routing': {
            'app.apptshardedmodel': {
                'write': 'test1',
                'read': 'test2',
            }
        }
    },
    DATABASES={
        'test1__{}'.format(PID): {},
        'test2__{}'.format(PID): {}
    }
)
class ShardPerTenantQuerySetTestCase(TestCase):

    def setUp(self):
        ShardedPerTenantRouter._lookup_cache = {}

    def test_init(self):
        qs = TShardedModel.objects.get_queryset()

        self.assertDictEqual(qs._exact_lookups,  {})
        self.assertDictEqual(qs._hints, {})

    def test__clone(self):
        qs = TShardedModel.objects.filter(partner_id=PID)
        qs._exact_lookups = {'some': 'lookup'}

        clone_qs = qs._clone()

        self.assertFalse(id(qs._exact_lookups) == id(clone_qs._exact_lookups))
        self.assertDictEqual(qs._exact_lookups, clone_qs._exact_lookups)

    def test_filter_or_exclude(self):
        qs = TShardedModel.objects.filter(partner_id=1)
        self.assertDictEqual(qs._exact_lookups,  {'partner_id': PID})

    def test_using_replica(self):
        qs = TShardedModel.objects.using('replica')
        self.assertEqual(qs._db, 'replica')

    def test_using_master(self):
        qs = TShardedModel.objects.using('master')
        self.assertEqual(qs._db, 'master')

    def test_db(self):
        qs = TShardedModel.objects.filter(partner_id=PID)
        alias = qs.db
        self.assertEqual(alias, 'test2__{}'.format(PID))

    def test_db_for_replica(self):
        qs = TShardedModel.objects.using('replica').filter(partner_id=PID)
        alias = qs.db
        self.assertEqual(alias, 'test2__{}__replica'.format(PID))

    @override_settings(
        DATABASE_ROUTERS=['shardy.db_routers.ShardedPerTenantRouter'],
        DEFAULT_DB_GROUP='test_db_group',
        DATABASE_CONFIG={'routing': {}},
        DATABASES={
            'test_db_group__{}'.format(PID): {},
        }
    )
    def test_db_for_default(self):
        qs = TShardedModel.objects.filter(partner_id=PID)
        alias = qs.db
        self.assertEqual(alias, 'test_db_group__{}'.format(PID))

    @override_settings(
        DATABASE_ROUTERS=['shardy.db_routers.ShardedPerTenantRouter'],
        DEFAULT_DB_GROUP='test_db_group',
        DATABASE_CONFIG={'routing': {}},
        DATABASES={
            'test_db_group__{}'.format(PID): {},
        }
    )
    def test_db_for_default_replica(self):
        qs = TShardedModel.objects.using('replica').filter(partner_id=PID)
        alias = qs.db
        self.assertEqual(alias, 'test_db_group__{}__replica'.format(PID))

    @override_settings(
        DATABASE_ROUTERS=['shardy.db_routers.ShardedPerTenantRouter'],
        DEFAULT_DB_GROUP='default',
        DATABASE_CONFIG={'routing': {}},
    )
    def test_create(self):
        qs = TShardedModel.objects.get_queryset()
        qs.create(partner_id=PID)
        self.assertEqual(qs._exact_lookups, {'partner_id': PID})

    @override_settings(
        DATABASE_ROUTERS=['shardy.db_routers.ShardedPerTenantRouter'],
        DEFAULT_DB_GROUP='default',
        DATABASE_CONFIG={'routing': {}},
    )
    def test_get_or_create(self):
        qs = TShardedModel.objects.get_queryset()
        qs.create(partner_id=PID)
        self.assertEqual(qs._exact_lookups, {'partner_id': PID})

    @override_settings(
        DATABASE_ROUTERS=['shardy.db_routers.ShardedPerTenantRouter'],
        DEFAULT_DB_GROUP='default',
        DATABASE_CONFIG={'routing': {}},
    )
    def test_bulk_create_correct_flow(self):
        self.assertFalse(TShardedModel.objects.filter(partner_id=PID).count())
        objects = [
            TShardedModel(partner_id=PID),
            TShardedModel(partner_id=str(PID)),
            TShardedModel(partner_id=str(PID)),
        ]
        TShardedModel.objects.bulk_create(objects)

        self.assertEqual(
            TShardedModel.objects.filter(partner_id=PID).count(),
            3
        )

    @override_settings(
        DATABASE_ROUTERS=['shardy.db_routers.ShardedPerTenantRouter'],
        DEFAULT_DB_GROUP='default',
        DATABASE_CONFIG={'routing': {}},
    )
    def test_bulk_create_incorrect_flow(self):
        objects = [
            TShardedModel(partner_id=PID),
            TShardedModel(partner_id=None),
        ]
        with self.assertRaises(ShardPerTenantQuerySetBulkCreate):
            TShardedModel.objects.bulk_create(objects)

        objects = [
            TShardedModel(partner_id=PID),
            TShardedModel(partner_id=PID + 1),
        ]
        with self.assertRaises(ShardPerTenantQuerySetBulkCreate):
            TShardedModel.objects.bulk_create(objects)
