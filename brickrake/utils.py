"""
Utility methods
"""
import itertools
import math
import urllib.error
import urllib.parse
import urllib.parse
import urllib.request

import requests

from bs4 import BeautifulSoup as BS


hdr = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
    'Accept-Encoding': 'none',
    'Accept-Language': 'en-US,en;q=0.8',
    'Connection': 'keep-alive'}


def beautiful_soup(url):
    """Fetch a web page and return its contents as parsed by Beautiful Soup"""
    return BS(requests.get(url, hdr=hdr).text)


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
