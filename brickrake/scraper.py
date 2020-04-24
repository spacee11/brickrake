"""
Functions for scraping bricklink.com
"""
import re
import ast
import urllib.error
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup as BS

from . import color
from . import utils


def price_guide(item, max_cost_quantile=None):
    """Fetch pricing info for an item"""
    results = []

    if (item['ItemTypeID'] == 'P' and 'stk0' in item['ItemID']) or \
            item['ItemTypeID'] == 'S' or \
            item['ItemTypeID'] == 'M':
        # a sticker sheet, a set, or a minifigure
        color_ids = [0]
    else:
        # a normal item
        color_ids = color.similar_to(item['ColorID'])

    for c in color_ids:
        # perform HTTP request
        parameters = {
            'itemType': item['ItemTypeID'],
            'itemNo': item['ItemID'],
            'itemSeq': 1,
            'colorId': c,
            'v': 'P',
            'priceGroup': 'Y',
            'prDec': 2
        }
        url = "http://www.bricklink.com/catalogPG.asp?" + urllib.parse.urlencode(parameters)
        html = urllib.request.urlopen(url).read()

        # parse page
        page = BS(html)

        if len(page.find_all(text='Currently Available')) == 0:
            # not available in this color :(
            continue
        else:

            # newly found inventory
            new = []

            for td in page.find_all('td'):
                if td.find('a', recursive=False, href=re.compile('/store.asp')) is not None:
                    # find the td element with a link to a store. Its siblings contain
                    # the interesting bits like price and quantity available
                    store_url = td.find('a')['href']
                    store_id = int(utils.get_params(store_url)['sID'])
                    quantity = int(td.next_sibling.text)
                    cost_per_unit = float(re.findall('[0-9.]+',
                                                     td.next_sibling.next_sibling.text)[0])

                    new.append({
                        'item_id': item['ItemID'],
                        'wanted_color_id': item['ColorID'],
                        'color_id': c,
                        'store_id': store_id,
                        'quantity_available': quantity,
                        'cost_per_unit': cost_per_unit
                    })

            # remove items that cost too much
            if max_cost_quantile is not None and max_cost_quantile < 1.0:
                observed_prices = [e['quantity_available'] * [e['cost_per_unit']] for e in new]
                observed_prices = list(sorted(utils.flatten(observed_prices)))
                if len(observed_prices) > 0:
                    i = utils.quantile(len(observed_prices) - 1, max_cost_quantile)
                    max_price = observed_prices[i]
                    new = [x for x in new if x['cost_per_unit'] <= max_price]

            # add what's left to the considered inventory
            results.extend(new)

        if sum(e['quantity_available'] for e in results) >= item['Qty']:
            # stop early, we've got everything we need
            return results

    return results


def store_info(country=None):
    """Fetch metadata for all stores"""
    browse_page = utils.beautiful_soup('https://www.bricklink.com/browse.asp')
    country_links = browse_page.find(
        'div', attrs={'class': 'column rightbuy'}).find_all(
        'a', attrs={'href': re.compile('countryID')})

    result = []

    for country_link in country_links:
        country_name = country_link.text
        country_id = utils.get_params(country_link['href'])['countryID']

        # skip this country link if we're only gathering data on one country
        if country is not None and country_id != country:
            continue

        country_page = utils.beautiful_soup('https://www.bricklink.com' + country_link['href'])
        store_links = country_page.find_all('a', href=re.compile('store.asp'))

        for store_link in store_links:
            store_page = utils.beautiful_soup('https://www.bricklink.com' + '/' + store_link['href'])
            raw_params = [x.contents[0] for x in store_page.find_all('script') if
                          (len(x.contents) > 0 and
                           (re.search('StoreFront.store *=', x.contents[0]) is not None))][0]
            store_params_str = re.search(
                r'StoreFront\.store = {[\s\S]*?};', raw_params).group(0)[len('StoreFront.store = ')::]
            store_params_str = re.sub('\t+\/\/.*\n', '', store_params_str)  # remove //comment lines
            store_params_str = re.sub('\r\n\r\n', '\r\n', re.sub('\t+\r\n', '', store_params_str))  # remove empty lines
            store_params_str = re.sub('\n\t+(.+?):',  # encase dict-like keys in parentheses
                                      lambda match: match.group(0).replace(
                                          match.group(1), '\'' + match.group(1) + '\''), store_params_str)
            for old, new in [['false', 'False'], ['true', 'True']]:  # some literal replacements
                store_params_str = store_params_str.replace(old, new)
            try:
                store_params = ast.literal_eval(store_params_str[:-1])  # evaluate modified string to python dict
            except:
                print(store_params_str)
                raise

            min_buy_str = store_params['minBuy']
            if min_buy_str is not '':
                currency_patterns = [  # basic list of currencies to match in minimum buy string, far from exhaustive
                    (r"US \$([0-9.]+)", 1),  # includes estimated conversion to USD
                    (r"US \$([0-9.]+)", 1.24),
                    (r"EUR ([0-9.]+)", 1.08),
                ]  # TODO add currency conversion / interpretation
                min_buy = None  # min_buy stays at None if currency was not found
                for re_pattern, conv_factor in currency_patterns:
                    min_buy_match = re.search(re_pattern, min_buy_str)
                    if min_buy_match is not None:
                        min_buy = float(min_buy_match.group(1)) * conv_factor
            else:
                min_buy = 0.0

            entry = {
                'store_name': store_params['name'],
                'store_id': int(store_params['id']),
                'country_name': store_params['countryName'],
                'country_id': store_params['countryID'],
                'seller_name': store_params['username'],
                'feedback': int(store_params['feedbackScore']),
                'minimum_buy': min_buy,
                'ships': store_params['shipsToBuyer']
            }
            print(entry)

            result.append(entry)

    return result


ALL_COUNTRIES = [
    "Argentina",
    "Australia",
    "Austria",
    "Belarus",
    "Belgium",
    "Bolivia",
    "Bosnia and Herzegovina",
    "Brazil",
    "Bulgaria",
    "Canada",
    "Chile",
    "China",
    "Croatia",
    "Czech Republic",
    "Denmark",
    "Ecuador",
    "El Salvador",
    "Estonia",
    "Finland",
    "France",
    "Germany",
    "Greece",
    "Guatemala",
    "Hong Kong",
    "Hungary",
    "Iceland",
    "India",
    "Indonesia",
    "Ireland",
    "Israel",
    "Italy",
    "Japan",
    "Jordan",
    "Latvia",
    "Lithuania",
    "Luxembourg",
    "Macau",
    "Malaysia",
    "Mexico",
    "Monaco",
    "Netherlands",
    "New Zealand",
    "Norway",
    "Pakistan",
    "Philippines",
    "Poland",
    "Portugal",
    "Romania",
    "Russia",
    "San Marino",
    "Serbia",
    "Singapore",
    "Slovakia",
    "Slovenia",
    "South Africa",
    "South Korea",
    "Spain",
    "Sweden",
    "Switzerland",
    "Syria",
    "Taiwan",
    "Thailand",
    "Trinidad and Tobago",
    "Turkey",
    "Ukraine",
    "United Kingdom",
    "USA",
    "Venezuela"
]
