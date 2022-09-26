# -*- coding: utf-8 -*-

try:
    from .core import *
    from .builtin_entities import *
    from .settings import *
    from . import erkloader
    from . import rdfstack
    from . import ruleengine
    from . import auxiliary as aux
    from .ackrep_parser import load_ackrep_entities
except ImportError:
    # this might be relevant during the installation process
    pass

from .release import __version__
