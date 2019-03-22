# coding=utf-8
import logging

from django.apps import apps

from django.forms.models import model_to_dict


app = apps.get_app_config('shardy')


class ShardPerTenantException(Exception):
    pass


class ShardPerTenantDBAliasException(Exception):
    pass


class ShardedPerTenantRouter(object):

    _lookup_cache = {}
    _write_mode = None

    def allow_relation(self, obj1, obj2, **hints):
        # Only allow relations if the objs are on the same shard
        model_name1 = obj1.__class__
        model_name2 = obj2.__class__
        if self._is_sharded_model(model_name1) and self._is_sharded_model(model_name2):
            self._write_mode = True
            return self._get_shard_for_instance(obj1) == self._get_shard_for_instance(obj2)
        return None

    def db_for_read(self, model, **hints):
        if self._is_sharded_model(model):
            self._write_mode = False
            return self._get_shard(model, **hints)
        return None

    def db_for_write(self, model, **hints):
        if self._is_sharded_model(model):
            self._write_mode = True
            return self._get_shard(model, **hints)
        return None

    @staticmethod
    def _is_sharded_model(model):
        from .models import ShardedPerTenantModel
        return issubclass(model, ShardedPerTenantModel)

    def _get_shard(self, model, **hints):
        if hints.get("instance", None):
            return self._get_shard_for_instance(instance=hints["instance"])

        try:
            exact_lookups = hints['exact_lookups']
        except KeyError:
            raise ShardPerTenantException(
                '{0} exact_lookups not found'.format(model.__name__)
            )

        try:
            shared_value = exact_lookups[model.sharded_field]
        except KeyError:
            raise ShardPerTenantException(
                '{0} {1} lookup must be filled'.format(
                    model.__name__, model.sharded_field
                )
            )

        return self._build_db_alias(shared_value, model)

    def _get_shard_for_instance(self, instance):
        if instance._state.db:
            return instance._state.db

        model = instance.__class__
        shared_value = instance.sharded_value
        if not shared_value:
            raise ShardPerTenantException(
                'Instance {0} must have {1} filled'.format(
                    model.__name__,
                    model.sharded_field
                )
            )

        return self._build_db_alias(shared_value, model)

    @classmethod
    def get_db_alias(cls, shard_value, model):
        return cls()._build_db_alias(shard_value, model)

    @staticmethod
    def load_sharded_db_connections():
        # TODO: 1) сделать комманду для миграции на основе системной, отличие только в формировании коннектов
        # TODO: 2) сделать автосоздание базы при заведении нового tenant (сигнал которые вешается на модель из конфига системы)
        # TODO: 3) переписать код ниже, чтобы он был более конфигурируемым, модель вынести в settings на примере USER_AUTH_MODEL

        from copy import copy
        from django.conf import settings
        from django.db import connections
        from app.models import Tenant

        for tenant in Tenant.objects.all():
            alias = 'default__{}'.format(tenant.id)
            if alias in settings.DATABASES:
                continue

            settings.DATABASES[alias] = copy(settings.DATABASES['default'])
            settings.DATABASES[alias]['NAME'] = 'postgres__{}'.format(tenant.id)
            connections.databases[alias] = copy(settings.DATABASES[alias])

    def _build_db_alias(self, shard_value, model):
        # TODO: придумать, как разделять виртуальный базы данных по "регионам"
        if self._is_sharded_model(model):
            self.load_sharded_db_connections()

        db_group = self._get_db_group(model)

        if not shard_value:
            return db_group

        if isinstance(shard_value, str):
            shard_value = int(shard_value)

        shard_db_alias = u'{}{}{}'.format(
            db_group,
            app.settings.SHARD_SEPARATOR,
            shard_value
        )
        if shard_db_alias not in app.settings.DATABASES:
            raise ShardPerTenantException(
                'DB alias `{}` if undefined'.format(shard_db_alias)
            )
        return shard_db_alias
    
    def _get_db_group(self, model):
        if model._meta.proxy:
            model = model._meta.proxy_for_model

        app_label = model._meta.app_label
        model_name = model._meta.model_name
        module_label = '%s.%s' % (app_label, model_name)
        mod_key = 'write' if self._write_mode else 'read'

        if module_label not in self._lookup_cache:
            conf = app.settings.DATABASE_CONFIG.get('routing', {})
            if module_label in conf:
                result = conf[module_label]
            elif app_label in conf:
                result = conf[app_label]
            else:
                result = {
                    'write': app.settings.DEFAULT_DB_GROUP,
                    'read': app.settings.DEFAULT_DB_GROUP,
                }

            self._lookup_cache[module_label] = result

        return self._lookup_cache[module_label][mod_key]


class ShardedPerTenantRouterLogger(ShardedPerTenantRouter):

    logger = logging.getLogger('shared_per_tenant_router')

    def db_for_read(self, model, **hints):
        if self._is_sharded_model(model):
            self._extract_shared_value(model, **hints)
        return None

    def db_for_write(self, model, **hints):
        if self._is_sharded_model(model):
            self._extract_shared_value(model, **hints)
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def _extract_shared_value(self, model, **hints):
        shared_value = None
        if hints.get("instance", None):
            instance = hints['instance']
            shared_value = instance.sharded_value

            if not shared_value:
                self.logger.info(
                    self._stack(
                        'Instance of {0} should have {1} ({2})\n'.format(
                            instance.__class__.__name__,
                            model.sharded_field,
                            model_to_dict(instance)
                        )
                    )
                )
            return shared_value

        try:
            exact_lookups = hints['exact_lookups']
        except KeyError:
            self.logger.info(
                self._stack(
                    '{0} exact_lookups not found ({1})\n'.format(
                        model.__name__,
                        hints
                    )
                )
            )
            return shared_value

        try:
            shared_value = exact_lookups[model.sharded_field]
        except KeyError:
            self.logger.info(
                self._stack(
                    '{0} {1} lookup must be filled ({2})\n'.format(
                        model.__name__,
                        model.sharded_field,
                        exact_lookups
                    )
                )
            )
        return shared_value

    def _stack(self, message):
        import traceback
        stack = traceback.format_stack()
        stack.append(message)
        stack.append('=================================\n\n')
        return ''.join(stack)
