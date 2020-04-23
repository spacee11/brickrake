"""
Functions for loading/saving data
"""
import json
import xml.etree.ElementTree as ETree

from . import color
from . import utils

# conversion functions for specific fields in a BSX file
CONVERT = {
    'Qty': int,
    'Price': float,
    'OrigPrice': float,
    'OrigQty': int,
    'ColorID': int,
}

# Translate from BrickLink XML to BSX fields
TRANSLATIONS = {
    'ITEMID': 'ItemID',
    'ITEMTYPE': 'ItemTypeID',
    'COLOR': 'ColorID',
    'MINQTY': 'Qty'
}


def load_bsx(f):
    """Parse all items from a Brickstore Parts List XML file (*.bsx)

    Parameters
    ----------
    f : file-like object
        file containing XML contents"""
    root = ETree.parse(f)
    items = []
    for item in root.findall('.//Item'):
        item_dict = {}
        for child in list(item):
            tag = child.tag
            value = CONVERT.get(child.tag, lambda x: x)(child.text)
            item_dict[tag] = value
        items.append(item_dict)

    # sometimes there are multiple wanted lots with the same ItemID and ColorID.
    # Consolidate them together now.
    by_item = utils.groupby(items, lambda x: (x['ItemID'], x['ColorID']))
    result = []
    for ((item_id, color_id), same) in by_item.items():
        prototype = same[0]
        prototype['Qty'] = sum(e['Qty'] for e in same)
        result.append(prototype)
    return result


def load_xml(f):
    """Parse a BrickLink XML file"""
    root = ETree.parse(f)
    items = []
    for item in root.findall('.//ITEM'):
        item_dict = {}
        for child in list(item):
            tag = TRANSLATIONS.get(child.tag, child.tag)
            value = CONVERT.get(tag, lambda x: x)(child.text)
            item_dict[tag] = value
        item_dict['ItemName'] = item_dict['ItemID']
        item_dict['ColorName'] = color.name(item_dict['ColorID'])
        items.append(item_dict)

    # sometimes there are multiple wanted lots with the same ItemID and ColorID.
    # Consolidate them together now.
    by_item = utils.groupby(items, lambda x: (x['ItemID'], x['ColorID']))
    result = []
    for ((item_id, color_id), same) in by_item.items():
        prototype = same[0]
        prototype['Qty'] = sum(e['Qty'] for e in same)
        result.append(prototype)
    return result


def save_xml(f, allocation):
    """Save an allocation (brickrake.minimize output) as BrickLink XML"""
    # merge all items with the same (item id, color id)
    inventory = ETree.Element("Inventory")
    for row in allocation:
        item = ETree.SubElement(inventory, "Item")

        item_id = ETree.SubElement(item, "ITEMID")
        item_id.text = str(row['item_id'])

        color_id = ETree.SubElement(item, "COLOR")
        color_id.text = str(row['color_id'])

        minqty = ETree.SubElement(item, "MINQTY")
        minqty.text = str(int(row['quantity']))

        itemtype = ETree.SubElement(item, "ITEMTYPE")
        itemtype.text = "P"  # TODO this is a big assumption :(

        if 'wanted_list_id' in row and len(row['wanted_list_id']) > 0:
            wanted = ETree.SubElement(item, "WANTEDLISTID")
            wanted.text = row['wanted_list_id']

    ETree.ElementTree(inventory).write(f)
    return


def save_xml_per_vendor(folder, solution, stores):
    """Save a BrickLink XML with a Wanted List for each vendor"""
    stores = utils.groupby(stores, lambda x: x['store_id'])
    allocation = utils.groupby(solution['allocation'], lambda x: x['store_id'])
    # for each store
    for (store_id, group) in sorted(allocation.items()):
        store = stores[store_id][0]
        name = store['seller_name']

        # get wanted list id
        prompt = ("Create a new 'Wanted List' named '%s' and" +
                  " type its ID here: ") % (name,)
        wanted_list = input(prompt)

        # save that id onto the lot
        for lot in group:
            lot['wanted_list_id'] = wanted_list

    # write file
    allocation = utils.flatten(list(allocation.values()))
    with open(folder, 'w') as f:
        save_xml(f, allocation)


def load_price_guide(f):
    """Load pricing output"""
    return json.load(f)


def save_price_guide(f, price_guide):
    """Save pricing output"""
    json.dump(price_guide, f, indent=2)


def load_store_metadata(f):
    """Load metadata associated with stores"""
    return json.load(f)


def save_store_metadata(f, metadata):
    """Save metadata associated with stores"""
    json.dump(metadata, f, indent=2)


def load_solution(f):
    """Load a set of buying recommendations"""
    return json.load(f)


def save_solution(f, solutions):
    """Save a set of buying recommendations"""
    json.dump(solutions, f, indent=2)
