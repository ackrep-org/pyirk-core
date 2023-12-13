# -*- coding: utf-8 -*-

try:
    from .core import *
    from .builtin_entities import *
    from .settings import *
    from . import irkloader
    from . import rdfstack
    from . import ruleengine
    from . import auxiliary as aux
    from . import consistency_checking as cc
except ImportError:
    # this might be relevant during the installation process
    pass

from .release import __version__
