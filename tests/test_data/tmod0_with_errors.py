"""
This module serves to test the errorhandling of erkloader.
"""

import pyerk as p

__URI__ = "pyerk/testmodule0_with_errors"
p.register_mod(__URI__)
p.start_mod(__URI__)


I1000 = p.create_item(
    R1__has_label="test item in tmod0",
)

raise ValueError


p.end_mod()
