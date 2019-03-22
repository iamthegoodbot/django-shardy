# -*- coding: UTF-8 -*-


def get_all_model_master_db_aliases(model):
    """
    Get all master db_aliases for sharded model
    :param model:
    :return:
    """
    from skazka.stores.models import Store

    enabled_partner_ids = Store.objects.only_enabled('id')

    return set(model.get_db_alias(pid) for pid in enabled_partner_ids)


def get_all_model_replica_db_aliases(model):
    """
    Get all replication db_aliases for sharded model
    :param model:
    :return:
    """
    from skazka.stores.models import Store

    enabled_partner_ids = Store.objects.only_enabled('id')

    return set(model.get_db_alias(pid, using='replica') for pid in enabled_partner_ids)
