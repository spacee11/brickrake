"""
Utility methods
"""
import itertools
import math
import urllib.error
import urllib.parse
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup as BS


def beautiful_soup(url):
    """Fetch a web page and return its contents as parsed by Beautiful Soup"""
    return BS(urllib.request.urlopen(url).read())


def get_params(url):
    """Get HTML GET parameters from a URL"""
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    return dict((k, v[0]) for (k, v) in params.items())


def groupby(arr, kf=lambda x: x):
    """Create a dictionary mapping keys to objects with the same key"""
    result = itertools.groupby(sorted(arr, key=kf), kf)
    return dict((k, tuple(v)) for (k, v) in result)


def flatten(arr):
    """Flatten a nested array"""
    return list(itertools.chain(*arr))


def index(items):
    """Create a numerical index over a set of objects"""
    return dict((k, i) for (i, k) in enumerate(set(items)))


def quantile(n, p):
    return int(math.ceil(p * n))
