from uuid import uuid4

from django.db import models

from shardy.models import ShardedPerTenantModel


class Tenant(models.Model):
    name = models.TextField(default=str(uuid4()))


class AppTShardedModel(ShardedPerTenantModel):
    partner_id = models.IntegerField()
    name = models.CharField(max_length=10, null=True, blank=True)

    sharded_field = 'partner_id'

