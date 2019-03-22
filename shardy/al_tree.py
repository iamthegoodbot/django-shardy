# coding=utf-8
"""Adjacency List"""
from treebeard.al_tree import AL_Node
from treebeard.exceptions import NodeAlreadySaved

from .managers import ShardedPerTenantManager
from .models import ShardedPerTenantModel


def get_result_class(cls):
    """
    For the given model class, determine what class we should use for the
    nodes returned by its tree methods (such as get_children).

    Usually this will be trivially the same as the initial model class,
    but there are special cases when model inheritance is in use:

    * If the model extends another via multi-table inheritance, we need to
      use whichever ancestor originally implemented the tree behaviour (i.e.
      the one which defines the 'parent' field). We can't use the
      subclass, because it's not guaranteed that the other nodes reachable
      from the current one will be instances of the same subclass.

    * If the model is a proxy model, the returned nodes should also use
      the proxy class.
    """
    base_class = cls._meta.get_field('parent').model
    if cls._meta.proxy_for_model == base_class:
        return cls
    else:
        return base_class


class AL_ShardedNodeManager(ShardedPerTenantManager):
    """Custom manager for nodes in an Adjacency List tree."""
    def get_queryset(self):
        """Sets the custom queryset as the default."""
        if self.model.node_order_by:
            order_by = ['parent'] + list(self.model.node_order_by)
        else:
            order_by = ['parent', 'sib_order']
        return super(AL_ShardedNodeManager, self).get_queryset().order_by(*order_by)


class AL_ShardedPerTenantNode(AL_Node, ShardedPerTenantModel):
    """Abstract model to create your own Adjacency List Trees."""

    objects = AL_ShardedNodeManager()
    node_order_by = None

    class Meta:
        """Abstract model."""
        abstract = True

    @classmethod
    def get_root_nodes(cls, shared_value):
        """:returns: A queryset containing the root nodes in the tree."""
        lookup = {
            cls.sharded_field: shared_value,
            'parent__isnull': True
        }
        return get_result_class(cls).objects.filter(**lookup)

    def get_children(self):
        """:returns: A queryset of all the node's children"""
        lookup = {
            self.sharded_field: getattr(self, self.sharded_field),
            'parent': self
        }
        return get_result_class(self.__class__).objects.filter(**lookup)

    def get_parent(self, update=False):
        """:returns: the parent node of the current node object."""
        if self._meta.proxy_for_model:
            # the current node is a proxy model; the returned parent
            # should be the same proxy model, so we need to explicitly
            # fetch it as an instance of that model rather than simply
            # following the 'parent' relation
            if self.parent_id is None:
                return None
            else:
                lookup = {
                    self.sharded_field: getattr(self, self.sharded_field),
                    'pk': self.parent_id,
                }
                return self.__class__.objects.get(**lookup)
        else:
            return self.parent

    def get_ancestors(self):
        """
        :returns: A *list* containing the current node object's ancestors,
            starting by the root node and descending to the parent.
        """
        ancestors = []
        if self._meta.proxy_for_model:
            # the current node is a proxy model; our result set
            # should use the same proxy model, so we need to
            # explicitly fetch instances of that model
            # when following the 'parent' relation
            cls = self.__class__
            node = self
            while node.parent_id:
                lookup = {
                    self.sharded_field: getattr(self, self.sharded_field),
                    'pk': node.parent_id,
                }
                node = cls.objects.get(**lookup)
                ancestors.insert(0, node)
        else:
            node = self.parent
            while node:
                ancestors.insert(0, node)
                node = node.parent
        return ancestors

    @classmethod
    def dump_bulk(cls, parent=None, keep_ids=True):
        """Dumps a tree branch to a python data structure."""
        raise NotImplementedError

    def add_child(self, **kwargs):
        """Adds a child to the node."""
        cls = get_result_class(self.__class__)

        if len(kwargs) == 1 and 'instance' in kwargs:
            # adding the passed (unsaved) instance to the tree
            newobj = kwargs['instance']
            if newobj.pk:
                raise NodeAlreadySaved("Attempted to add a tree node that is "\
                    "already in the database")
        else:
            newobj = cls(**kwargs)

        try:
            newobj._cached_depth = self._cached_depth + 1
        except AttributeError:
            pass
        if not cls.node_order_by:
            try:
                lookup = {
                    self.sharded_field: getattr(self, self.sharded_field),
                    'parent': self,
                }
                max = cls.objects.filter(**lookup).reverse()[0].sib_order
            except IndexError:
                max = 0
            newobj.sib_order = max + 1
        newobj.parent = self
        newobj.save()
        return newobj

    @classmethod
    def _get_tree_recursively(cls, shared_value, results, parent, depth):
        if parent:
            nodes = parent.get_children()
        else:
            nodes = cls.get_root_nodes(shared_value)
        for node in nodes:
            node._cached_depth = depth
            results.append(node)
            cls._get_tree_recursively(shared_value, results, node, depth + 1)

    @classmethod
    def get_tree(cls, shared_value, parent=None):
        """
        :returns: A list of nodes ordered as DFS, including the parent. If
                  no parent is given, the entire tree is returned.
        """
        if parent:
            depth = parent.get_depth() + 1
            results = [parent]
        else:
            depth = 1
            results = []
        cls._get_tree_recursively(shared_value, results, parent, depth)
        return results

    def get_descendants(self):
        """
        :returns: A *list* of all the node's descendants, doesn't
            include the node itself
        """
        lookup = {
            self.sharded_field: getattr(self, self.sharded_field),
            'parent': self,
        }
        return self.__class__.get_tree(**lookup)[1:]

    def move(self, target, pos=None):
        """
        Moves the current node and all it's descendants to a new position
        relative to another node.
        """
        # пока не используем этот метод для шардированных моделей
        raise NotImplementedError

    def delete(self):
        """Removes a node and all it's descendants."""
        lookup = {
            self.sharded_field: getattr(self, self.sharded_field),
            'pk': self.pk,
        }
        self.__class__.objects.filter(**lookup).delete()