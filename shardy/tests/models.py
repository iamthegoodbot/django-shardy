from django.db import models

from shardy.models import ShardedPerTenantModel


class TShardedModel(ShardedPerTenantModel):
    partner_id = models.IntegerField()
    name = models.CharField(max_length=10, null=True, blank=True)

    sharded_field = 'partner_id'


class TShardedUndefinedModel(ShardedPerTenantModel):
    partner_id = models.IntegerField()

    sharded_field = None


class TShardedUnexpectedModel(ShardedPerTenantModel):
    partner_id = models.IntegerField()

    sharded_field = 'partner_id1'


class TNoneShardedModel(models.Model):
    partner_id = models.IntegerField()

    class Meta:
        app_label = 'sharding_utils'
