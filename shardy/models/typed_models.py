import types

import django
from django.db import models
from django.db.models import Field
from django.utils.six import with_metaclass
from typedmodels.models import TypedModelMetaclass

from models import (
    ShardedTypedModel,
)
from models.common import ShardedPerTenantModel, ShardedTypedModelManager


class SharedTypedModelMetaclass(TypedModelMetaclass):
    """
    This metaclass enables a model for auto-downcasting using a ``type`` attribute.
    """
    def __new__(meta, classname, bases, classdict):
        # artifact created by with_metaclass, needed for py2/py3 compatibility
        if classname == 'NewBase':
            return super(SharedTypedModelMetaclass, meta).__new__(
                meta, classname, bases, classdict)
        try:
            ShardedTypedModel
        except NameError:
            # don't do anything for TypedModel class itself
            #
            # ...except updating Meta class to instantiate fields_from_subclasses attribute
            typed_model = super(SharedTypedModelMetaclass, meta).__new__(meta, classname, bases, classdict)
            # We have to set this attribute after _meta has been created, otherwise an
            # exception would be thrown by Options class constructor.
            typed_model._meta.fields_from_subclasses = {}
            return typed_model

        # look for a non-proxy base class that is a subclass of TypedModel
        mro = list(bases)
        while mro:
            base_class = mro.pop(-1)
            if issubclass(base_class, ShardedTypedModel) and base_class is not ShardedTypedModel:
                if base_class._meta.proxy:
                    # continue up the mro looking for non-proxy base classes
                    mro.extend(base_class.__bases__)
                else:
                    break
        else:
            base_class = None

        if base_class:
            # Enforce that subclasses are proxy models.
            # Update an existing metaclass, or define an empty one
            # then set proxy=True
            class Meta:
                pass
            Meta = classdict.get('Meta', Meta)
            if getattr(Meta, 'proxy', False):
                # If user has specified proxy=True explicitly, we assume that he wants it to be treated like ordinary
                # proxy class, without TypedModel logic.
                return super(TypedModelMetaclass, meta).__new__(meta, classname, bases, classdict)
            Meta.proxy = True

            declared_fields = dict((name, element) for name, element in classdict.items() if isinstance(element, Field))

            for field_name, field in declared_fields.items():
                # Warnings will be triggered by django's system
                # check for M2M fields setting if we set null to True. Prevent
                # those warnings by setting null only for non-M2M fields.
                if not field.many_to_many:
                    field.null = True
                if isinstance(field, models.fields.related.RelatedField):
                    # Monkey patching field instance to make do_related_class use created class instead of base_class.
                    # Actually that class doesn't exist yet, so we just monkey patch base_class for a while,
                    # changing _meta.model_name, so accessor names are generated properly.
                    # We'll do more stuff when the class is created.
                    old_do_related_class = field.do_related_class
                    def do_related_class(self, other, cls):
                        base_class_name = base_class.__name__
                        cls._meta.model_name = classname.lower()
                        old_do_related_class(other, cls)
                        cls._meta.model_name = base_class_name.lower()
                    field.do_related_class = types.MethodType(do_related_class, field)
                if isinstance(field, models.fields.related.RelatedField) and isinstance(field.rel.to, ShardedTypedModel) and field.rel.to.base_class:
                    field.rel.limit_choices_to['type__in'] = field.rel.to._typedmodels_subtypes
                    field.rel.to = field.rel.to.base_class
                field.contribute_to_class(base_class, field_name)
                classdict.pop(field_name)
            base_class._meta.fields_from_subclasses.update(declared_fields)

            # set app_label to the same as the base class, unless explicitly defined otherwise
            if not hasattr(Meta, 'app_label'):
                if hasattr(getattr(base_class, '_meta', None), 'app_label'):
                    Meta.app_label = base_class._meta.app_label

            classdict.update({
                'Meta': Meta,
            })

        classdict['base_class'] = base_class

        cls = super(TypedModelMetaclass, meta).__new__(meta, classname, bases, classdict)

        cls._meta.fields_from_subclasses = {}

        if base_class:
            opts = cls._meta

            model_name = opts.model_name
            typ = "%s.%s" % (opts.app_label, model_name)
            cls._typedmodels_type = typ
            cls._typedmodels_subtypes = [typ]
            if typ in base_class._typedmodels_registry:
                raise ValueError("Can't register %s type %r to %r (already registered to %r )" % (typ, classname, base_class._typedmodels_registry))
            base_class._typedmodels_registry[typ] = cls

            type_name = getattr(cls._meta, 'verbose_name', cls.__name__)
            type_field = base_class._meta.get_field('type')
            choices = tuple(list(type_field.choices) + [(typ, type_name)])
            choices_field = '_choices' if django.VERSION < (1, 9) else 'choices'
            setattr(type_field, choices_field, choices)

            cls._meta.declared_fields = declared_fields

            if django.VERSION < (1, 9):
                # Update related fields in base_class so they refer to cls.
                for field_name, related_field in declared_fields.items():
                    if isinstance(related_field, models.fields.related.RelatedField):
                        # Unfortunately RelatedObject is recreated in ./manage.py validate, so false positives for name clashes
                        # may be reported until #19399 is fixed - see https://code.djangoproject.com/ticket/19399
                        related_field.related.opts = cls._meta

            # look for any other proxy superclasses, they'll need to know
            # about this subclass
            for superclass in cls.mro():
                if (issubclass(superclass, base_class)
                        and superclass not in (cls, base_class)
                        and hasattr(superclass, '_typedmodels_type')):
                    superclass._typedmodels_subtypes.append(typ)

            meta._patch_fields_cache(cls, base_class)
        else:
            # this is the base class
            cls._typedmodels_registry = {}

            # Since fields may be added by subclasses, save original fields.
            cls._meta._typedmodels_original_fields = cls._meta.fields
            cls._meta._typedmodels_original_many_to_many = cls._meta.many_to_many

            # add a get_type_classes classmethod to allow fetching of all the subclasses (useful for admin)

            def get_type_classes(subcls):
                if subcls is cls:
                    return list(cls._typedmodels_registry.values())
                else:
                    return [cls._typedmodels_registry[k] for k in subcls._typedmodels_subtypes]
            cls.get_type_classes = classmethod(get_type_classes)

            def get_types(subcls):
                if subcls is cls:
                    return cls._typedmodels_registry.keys()
                else:
                    return subcls._typedmodels_subtypes[:]
            cls.get_types = classmethod(get_types)

        return cls


class ShardedTypedModel(with_metaclass(SharedTypedModelMetaclass, ShardedPerTenantModel)):
    '''
    This class contains the functionality required to auto-downcast a model based
    on its ``type`` attribute.

    To use, simply subclass TypedModel for your base type, and then subclass
    that for your concrete types.
    '''
    objects = ShardedTypedModelManager()

    type = models.CharField(choices=(), max_length=255, null=False, blank=False, db_index=True)

    # Class variable indicating if model should be automatically recasted after initialization
    _auto_recast = True

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        # Calling __init__ on base class because some functions (e.g. save()) need access to field values from base
        # class.

        # Move args to kwargs since base_class may have more fields defined with different ordering
        args = list(args)
        if len(args) > len(self._meta.fields):
            # Daft, but matches old exception sans the err msg.
            raise IndexError("Number of args exceeds number of fields")
        for field_value, field in zip(args, self._meta.fields):
            kwargs[field.attname] = field_value
        args = []  # args were all converted to kwargs

        if self.base_class:
            before_class = self.__class__
            self.__class__ = self.base_class
        else:
            before_class = None
        super(ShardedTypedModel, self).__init__(*args, **kwargs)
        if before_class:
            self.__class__ = before_class
        if self._auto_recast:
            self.recast()

    def recast(self, typ=None):
        if not self.type:
            if not hasattr(self, '_typedmodels_type'):
                # Ideally we'd raise an error here, but the django admin likes to call
                # model() and doesn't expect an error.
                # Instead, we raise an error when the object is saved.
                return
            self.type = self._typedmodels_type

        for base in self.__class__.mro():
            if issubclass(base, ShardedTypedModel) and hasattr(base, '_typedmodels_registry'):
                break
        else:
            raise ValueError("No suitable base class found to recast!")

        if typ is None:
            typ = self.type
        else:
            if isinstance(typ, type) and issubclass(typ, base):
                if django.VERSION < (1, 7):
                    model_name = typ._meta.module_name
                else:
                    model_name = typ._meta.model_name
                typ = '%s.%s' % (typ._meta.app_label, model_name)

        try:
            correct_cls = base._typedmodels_registry[typ]
        except KeyError:
            raise ValueError("Invalid %s identifier: %r" % (base.__name__, typ))

        self.type = typ

        current_cls = self.__class__

        if current_cls != correct_cls:
            if django.VERSION < (1, 10) and self._deferred:
                # older django used a special class created on the fly for deferred model instances.
                # So we need to create a new deferred class based on correct_cls instead of current_cls
                from django.db.models.query_utils import DeferredAttribute, deferred_class_factory
                attrs = [k for (k, v) in current_cls.__dict__.items() if isinstance(v, DeferredAttribute)]
                correct_cls = deferred_class_factory(correct_cls, attrs)
            self.__class__ = correct_cls

    def save(self, *args, **kwargs):
        if not getattr(self, '_typedmodels_type', None):
            raise RuntimeError("Untyped %s cannot be saved." % self.__class__.__name__)
        return super(ShardedTypedModel, self).save(*args, **kwargs)

