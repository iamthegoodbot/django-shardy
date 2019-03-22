from django import apps
from django.db import router
from django.db.models import QuerySet
from django.db.models.query import RawQuerySet

from django.apps import apps


app = apps.get_app_config('shardy')


class ShardPerTenantQuerySetBulkCreate(Exception):
    pass


class ReplicaAlias(object):

    def __init__(self, alias):
        self._alias = alias

    def get(self, alias_suffix):
        """
           db_2__1127 -> db_2__1127__replica

           db_2 -> db_2__replica

        :return: replica aliase
        """
        if app.settings.SHARD_SEPARATOR in self._alias:
            db_group, shard_id = self._alias.split(
                app.settings.SHARD_SEPARATOR
            )
            replica = app.settings.SHARD_SEPARATOR.join(
                [db_group, shard_id, alias_suffix]
            )
        else:
            replica = app.settings.SHARD_SEPARATOR.join(
                [self._alias, alias_suffix]
            )
        return replica



class ShardPerTenantQuerySet(QuerySet):
    """
    Stores the lookups to pass to the router as a hint
    """
    def __init__(self, model=None, query=None, using=None, hints=None, *args, **kwargs):
        super(ShardPerTenantQuerySet, self).__init__(
            model=model, query=query, using=using
        )
        self._hints = hints or {}
        self._exact_lookups = {}

    def _clone(self, **kwargs):
        clone = super(ShardPerTenantQuerySet, self)._clone(**kwargs)
        clone._exact_lookups = self._exact_lookups.copy()
        return clone

    def _filter_or_exclude(self, *args, **kwargs):
        """
        Update our lookups when we get a filter or an exclude
        (we only care about filter, but its a shared function in the ORM)
        :return:
        """
        clone = (
            super(ShardPerTenantQuerySet, self)
            ._filter_or_exclude(*args, **kwargs)
        )
        if getattr(clone, '_exact_lookups', None) is None:
            clone._exact_lookups = {}
        clone._exact_lookups.update(
            dict([(k, v) for k, v in kwargs.items() if '__' not in k])
        )
        return clone

    @property
    def db(self):
        self._hints['exact_lookups'] = self._exact_lookups
        if not self._hints.get('instance') and getattr(self, '_instance', None):
            self._hints['instance'] = getattr(self, '_instance')

        if self._for_write:
            alias = router.db_for_write(self.model, **self._hints)
        else:
            alias = router.db_for_read(self.model, **self._hints)

        if self._db and self._db != alias:
            alias = ReplicaAlias(alias).get(self._db)

        return alias

    def create(self, **kwargs):
        """
        Grabs the instance before its too late to pass it to the router
        as a hint. Django (as of 1.9) does not keep instances around in all
        cases, such as a create() call.
        """
        self._instance = self.model(**kwargs.copy())
        lookup, params = self._extract_model_params({}, **kwargs)
        self._exact_lookups = lookup
        return super(ShardPerTenantQuerySet, self).create(**kwargs)

    def get_or_create(self, defaults=None, **kwargs):
        """
        Add the lookups to the _exact_lookups and call super.
        """
        defaults = defaults or {}
        lookup, params = self._extract_model_params(defaults, **kwargs)
        self._exact_lookups = lookup
        return (
            super(ShardPerTenantQuerySet, self)
            .get_or_create(defaults=defaults, **kwargs)
        )

    def bulk_create(self, objs, batch_size=None):
        if objs:
            sharded_field = objs[0].__class__.sharded_field
            shared_values = {
                obj.sharded_value for obj in objs
            }
            shared_values = {int(val) if val else val for val in shared_values}
            if len(shared_values) != 1:
                raise ShardPerTenantQuerySetBulkCreate

            self._exact_lookups[sharded_field] = shared_values.pop()
        return (
            super(ShardPerTenantQuerySet, self)
            .bulk_create(objs=objs, batch_size=batch_size)
        )

    def only(self, *fields):
        if fields == (None,):
            # Can only pass None to defer(), not only(), as the rest option.
            # That won't stop people trying to do this, so let's be explicit.
            raise TypeError("Cannot pass None as an argument to only().")

        if self.model.sharded_field not in fields:
            fields = list(fields)
            fields.append(self.model.sharded_field)
        return super(ShardPerTenantQuerySet, self).only(*fields)


class ShardRawPerTenantQuerySet(ShardPerTenantQuerySet, RawQuerySet):

    def __init__(self, *args, **kwargs):
        super(ShardRawPerTenantQuerySet, self).__init__(*args, **kwargs)
