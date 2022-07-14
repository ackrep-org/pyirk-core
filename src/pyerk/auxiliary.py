from typing import Iterable

"""
Some auxiliary classes for pyerk.
"""


class OneToOneMapping(object):
    def __init__(self, **kwargs):
        self.a = dict(**kwargs)
        self.b = dict([(v, k) for k, v in kwargs.items()])

        # assert 1to1-property
        assert len(self.a) == len(self.b)

    def add_pair(self, key_a, key_b):
        self.a[key_a] = key_b
        self.b[key_b] = key_a

        # assert 1to1-property
        assert len(self.a) == len(self.b)

    def remove_pair(self, key_a=None, key_b=None):

        if key_a is not None:
            key_b = self.a.pop(key_a)
            self.b.pop(key_b)
        elif key_b is not None:
            key_a = self.b.pop(key_b)
            self.a.pop(key_a)
        else:
            msg = "Both keys are not allowed to be `None` at the the same time."
            raise ValueError(msg)


def ensure_list(arg):
    if not isinstance(arg, list):
        return [arg]
    else:
        return arg


class ListWithAttributes(list):
    """
    This subclass of list can have attributes
    """

    var: Iterable


def apply_func_to_table_cells(func: callable, table: Iterable, *args, **kwargs) -> ListWithAttributes:
    res = ListWithAttributes()
    for row in table:
        new_row = []
        for cell in row:
            new_row.append(func(cell, *args, **kwargs))
        res.append(new_row)

    return res
