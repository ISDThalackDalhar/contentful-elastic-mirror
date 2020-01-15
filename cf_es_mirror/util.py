from typing import Any, Optional, Callable, Union, List

try:
    from flask.helpers import locked_cached_property as cached_property
except:
    from django.utils.functional import cached_property


def get_path(data, *path, default=None):
    obj = data
    for part in path:
        if part not in obj:
            if isinstance(default, Exception):
                raise default
            else:
                return default
        else:
            obj = obj[part]
    return obj


def try_int(x: Any, default: Any = None):
    try:
        return int(x)
    except:
        return default


def split_list(x: str, sep: str = ',', default: Any = None, maxsplit: int = -1):
    if not x:
        return default
    if isinstance(x, list):
        return x
    if isinstance(x, tuple):
        return list(x)
    x = list(x.split(sep, maxsplit=maxsplit))
    return x or default


def split_dict(x: str, sep: str = ',', valsep: str = '=', default: Any = None):
    x = split_list(x, sep=sep, default=None)
    if not x:
        return default
    assert all(valsep in y for y in x), "Dict values must be in the format 'key%svalue'" % valsep
    return {key: val for key, val in [y.split(valsep, 1) for y in x]}


def to_bool(x: str, default: Any = False):
    if x is None:
        return default
    if isinstance(x, bool):
        return x
    if isinstance(x, str):
        x = x.lower()
    if x in (True, 'yes', 1, '1', 'y'):
        return True
    elif x in (False, 'no', 0, '0', 'n'):
        return False
    return default


def to_int(x: str, default: Any = 0):
    if x is None:
        return default
    if isinstance(x, int):
        return x
    return try_int(x, default)


def merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict):
            n = a.setdefault(k, {})
            merge(n, v)
        else:
            a[k] = v
    return a


__all__ = [
    'to_int',
    'try_int',
    'to_bool',
    'split_list',
    'split_dict',
    'cached_property',
    'get_path',
]