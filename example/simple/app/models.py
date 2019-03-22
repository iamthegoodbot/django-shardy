from django.db import models

# Create your models here.
from shardy.models import ShardedPerTenantModel


class AppTShardedModel(ShardedPerTenantModel):
    partner_id = models.IntegerField()
    name = models.CharField(max_length=10, null=True, blank=True)

    sharded_field = 'partner_id'

