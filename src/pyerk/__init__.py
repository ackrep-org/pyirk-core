# -*- coding: utf-8 -*-

try:
    from .core import *
    from . import erkloader
except ImportError:
    # this might be relevant during the installation process
    pass

from .release import __version__
