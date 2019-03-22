# coding=utf-8

from .common import *

try:
    from typedmodels.models import TypedModelMetaclass
    from .typed_models import *
except ImportError:
    pass
