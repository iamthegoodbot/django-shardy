from random import randint
from unittest import mock

from django.forms.models import model_to_dict
from django.test import TestCase
from django.test.utils import override_settings

from shardy.db_routers import (
    ShardedPerTenantRouter,
    ShardedPerTenantRouterLogger
)
from shardy.tests.models import (
    TShardedModel,
    TNoneShardedModel
)

PID = 1

@override_settings(
    DATABASE_CONFIG={
        'routing': {
            'shardy.tshardedmodel': {
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
class ShardedPerTenantRouterTestCase(TestCase):

    def setUp(self):
        ShardedPerTenantRouter._lookup_cache = {}

    def test_get_db_group_for_read(self):
        router = ShardedPerTenantRouter()
        router._write_mode = False
        db_group = router._get_db_group(TShardedModel)

        self.assertEqual(db_group, 'test2')

    def test_get_db_group_for_write(self):
        router = ShardedPerTenantRouter()
        router._write_mode = True
        db_group = router._get_db_group(TShardedModel)

        self.assertEqual(db_group, 'test1')

    @override_settings(
        DEFAULT_DB_GROUP='default_test'
    )
    def test_get_db_group_for_default(self):
        router = ShardedPerTenantRouter()
        router._write_mode = True
        db_group = router._get_db_group(TShardedModel)

        self.assertEqual(db_group, 'test1')

    def test__build_db_alias_with_config(self):
        router = ShardedPerTenantRouter()
        router._write_mode = True
        db_alias = router._build_db_alias(1, TShardedModel)

        self.assertEqual(db_alias, 'test1__1')

    def test__build_db_alias_without_shard_value(self):
        router = ShardedPerTenantRouter()
        router._write_mode = True
        db_alias = router._build_db_alias(None, TShardedModel)

        self.assertEqual(db_alias, 'test1')

    def test_get_shard_for_instance_write_mod(self):
        instance = TShardedModel(partner_id=PID)
        router = ShardedPerTenantRouter()
        router._write_mode = True
        db_alias = router._get_shard_for_instance(instance)

        self.assertEqual(db_alias, 'test1__{}'.format(instance.partner_id))

    def test_get_shard_for_instance_read_mod(self):
        instance = TShardedModel(partner_id=PID)
        router = ShardedPerTenantRouter()
        router._write_mode = False
        db_alias = router._get_shard_for_instance(instance)

        self.assertEqual(db_alias, 'test2__{}'.format(instance.partner_id))

    def test_get_shard_with_instance_write_mode(self):
        router = ShardedPerTenantRouter()
        router._write_mode = True
        instance = TShardedModel(partner_id=PID)
        hints = {'instance': instance}
        db_alias = router._get_shard(TShardedModel, **hints)

        self.assertEqual(db_alias, 'test1__{}'.format(instance.partner_id))

    def test_get_shard_with_instance_read_mode(self):
        router = ShardedPerTenantRouter()
        router._write_mode = False
        instance = TShardedModel(partner_id=PID)
        hints = {'instance': instance}
        db_alias = router._get_shard(TShardedModel, **hints)

        self.assertEqual(db_alias, 'test2__{}'.format(instance.partner_id))

    def test_get_shard_write_mode(self):
        partner_id = PID
        router = ShardedPerTenantRouter()
        router._write_mode = True
        hints = {
            'exact_lookups': {
                TShardedModel.sharded_field: partner_id
            }
        }
        db_alias = router._get_shard(TShardedModel, **hints)

        self.assertEqual(db_alias, 'test1__{}'.format(partner_id))

    def test_get_shard_read_mode(self):
        partner_id = PID
        router = ShardedPerTenantRouter()
        router._write_mode = False
        hints = {
            'exact_lookups': {
                TShardedModel.sharded_field: partner_id
            }
        }
        db_alias = router._get_shard(TShardedModel, **hints)

        self.assertEqual(db_alias, 'test2__{}'.format(partner_id))

    def test_is_sharded_model(self):
        router = ShardedPerTenantRouter()
        self.assertTrue(router._is_sharded_model(TShardedModel))
        self.assertFalse(router._is_sharded_model(TNoneShardedModel))

    def test_db_for_write_for_non_sharded_model(self):
        router = ShardedPerTenantRouter()
        self.assertIsNone(router.db_for_write(TNoneShardedModel))

    def test_db_for_write(self):
        router = ShardedPerTenantRouter()
        obj = TShardedModel(partner_id=PID)
        db_alias = router.db_for_write(TShardedModel, instance=obj)

        self.assertEqual(db_alias, 'test1__{}'.format(obj.partner_id))
        self.assertTrue(router._write_mode)

    def test_db_for_read_for_non_sharded_model(self):
        router = ShardedPerTenantRouter()
        self.assertIsNone(router.db_for_write(TNoneShardedModel))

    def test_db_for_read(self):
        router = ShardedPerTenantRouter()
        obj = TShardedModel(partner_id=PID)
        db_alias = router.db_for_read(TShardedModel, instance=obj)

        self.assertEqual(db_alias, 'test2__{}'.format(obj.partner_id))
        self.assertFalse(router._write_mode)

    def test_allow_relation(self):
        router = ShardedPerTenantRouter()
        obj1 = TShardedModel(partner_id=PID)
        obj2 = TShardedModel(partner_id=obj1.partner_id)
        result = router.allow_relation(obj1, obj2)

        self.assertTrue(result)
        self.assertTrue(router._write_mode)

    @override_settings(
        DATABASE_CONFIG={
            'routing': {
                'shardy.tshardedmodel': {
                    'write': 'test1',
                    'read': 'test2',
                }
            }
        },
        DATABASES={
            'test1': {},
            'test2': {}
        }
    )
    def test_if_alias_not_in_DATABASES_then_return_db_group(self):
        router = ShardedPerTenantRouter()
        router._write_mode = True
        db_alias = router._build_db_alias(1, TShardedModel)

        self.assertEqual(db_alias, 'test1')


class ShardedPerTenantRouterLoggerTestCase(TestCase):

    def setUp(self):
        self.PID = randint(1000, 10000)
        self.router = ShardedPerTenantRouterLogger()

    def test__extract_shared_value(self):
        hints = {
            'exact_lookups': {
                TShardedModel.sharded_field: self.PID
            }
        }

        val = self.router._extract_shared_value(TShardedModel, **hints)
        self.assertEqual(val, self.PID)

    def test__extract_shared_value_with_instance(self):
        obj = TShardedModel(partner_id=self.PID)
        hints = {'instance': obj}

        val = self.router._extract_shared_value(TShardedModel, **hints)
        self.assertEqual(val, self.PID)

    def test__extract_shared_value_should_logging_without_lookup(self):
        hints = {'some': 'hlam'}
        self.router._stack = mock.Mock(return_value='test_log_string')
        self.router.logger.info = mock.Mock()

        val = self.router._extract_shared_value(TShardedModel, **hints)
        self.assertIsNone(val)

        self.router._stack.assert_called_once_with(
            '{} exact_lookups not found ({})\n'.format(
                TShardedModel.__name__, hints
            )
        )
        self.router.logger.info.assert_called_once_with('test_log_string')

    def test__extract_shared_value_should_logging_with_empty_lookup(self):
        hints = {
            'exact_lookups': {
                'some': 'hlam'
            }
        }

        self.router._stack = mock.Mock(return_value='test_log_string')
        self.router.logger = mock.Mock()

        val = self.router._extract_shared_value(TShardedModel, **hints)
        self.assertIsNone(val)

        self.router.logger.info.assert_called_once_with('test_log_string')
        self.router._stack.assert_called_once_with(
            '{} {} lookup must be filled ({})\n'.format(
                TShardedModel.__name__,
                TShardedModel.sharded_field,
                hints['exact_lookups']
            )
        )

    def test__extract_shared_value_with_instance_should_logging_with_empty_sharded_value(self):
        obj = TShardedModel()
        hints = {
            'instance': obj
        }
        self.router._stack = mock.Mock(return_value='test_log_string')
        self.router.logger.info = mock.Mock()

        val = self.router._extract_shared_value(TShardedModel, **hints)

        self.assertIsNone(val)

        self.router.logger.info.assert_called_once_with('test_log_string')
        self.router._stack.assert_called_once_with(
            'Instance of {} should have {} ({})\n'.format(
                TShardedModel.__name__,
                TShardedModel.sharded_field,
                model_to_dict(obj)
            )
        )

    def test_db_for_write_should_call_extract_shared_only_for_sharded_model(self):
        hints = {'some': 'hlam'}
        self.router._extract_shared_value = mock.Mock()

        result = self.router.db_for_write(TShardedModel, **hints)

        self.assertIsNone(result)
        self.router._extract_shared_value.assert_called_once_with(
            TShardedModel, **hints
        )

    def test_db_for_write_should_do_nothing_for_none_sharded_model(self):
        hints = {'some': 'hlam'}
        self.router._extract_shared_value = mock.Mock()

        result = self.router.db_for_write(TNoneShardedModel, **hints)

        self.assertIsNone(result)
        self.router._extract_shared_value.assert_not_called()

    def test_db_for_read_should_call_extract_shared_only_for_sharded_model(self):
        hints = {'some': 'hlam'}
        self.router._extract_shared_value = mock.Mock()

        result = self.router.db_for_read(TShardedModel, **hints)

        self.assertIsNone(result)
        self.router._extract_shared_value.assert_called_once_with(
           TShardedModel, **hints
        )

    def test_db_for_read_should_do_nothing_for_none_sharded_model(self):
        hints = {'some': 'hlam'}
        self.router._extract_shared_value = mock.Mock()

        result = self.router.db_for_read(TNoneShardedModel, **hints)

        self.assertIsNone(result)
        self.router._extract_shared_value.assert_not_called()
