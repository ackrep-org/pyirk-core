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
