from django.db import models

from ..managers import ShardedPerTenantManager
from ..querysets import ReplicaAlias


class ShardedPerTenantModel(models.Model):

    """
    Явно указываем, из какого поля модели брать значение для формирования
    alias при подготовке коннекта к базе
    """
    sharded_field = None

    objects = ShardedPerTenantManager()

    class Meta:
        abstract = True

    @classmethod
    def get_db_alias(cls, sharded_value, using=None):
        """

        :param sharded_value: значение, по которому роутер определяе нужный шард
        :param using: str: вернет алиас c учтом суффикса using  shared_alias__[using]
        :return:
        """
        from ..db_routers import ShardedPerTenantRouter
        alias = ShardedPerTenantRouter.get_db_alias(sharded_value, cls)
        if using:
            alias = ReplicaAlias(alias).get(using)
        return alias

    @property
    def sharded_value(self):
        return getattr(self, self.sharded_field, None)

    def __init__(self, *args, **kwargs):
        if not self.sharded_field:
            raise SharedFieldIsUndefined(
                'sharded_field should be defined for {}'.format(
                    self.__class__.__name__
                )
            )

        super(ShardedPerTenantModel, self).__init__(*args, **kwargs)


class ShardedTypedModelManager(models.Manager):
    def get_queryset(self):
        qs = super(ShardedTypedModelManager, self).get_queryset()
        if hasattr(self.model, '_typedmodels_type'):
            if len(self.model._typedmodels_subtypes) > 1:
                qs = qs.filter(type__in=self.model._typedmodels_subtypes)
            else:
                qs = qs.filter(type=self.model._typedmodels_type)
        return qs


class SharedFieldIsUndefined(Exception):
    pass