import argparse
import os
import sys
import traceback

from brickrake import color
from brickrake import io
from brickrake import minimizer
from brickrake import scraper
from brickrake import utils


def price_guide(args_):
    """Scrape pricing information for all wanted parts"""
    # load in wanted parts
    if args_.parts_list.endswith(".bsx"):
        wanted_parts = io.load_bsx(open(args_.parts_list))
    else:
        wanted_parts = io.load_xml(open(args_.parts_list))
    print('Loaded %d different parts' % len(wanted_parts))

    # get prices for available parts
    fmt = "{i:4d} {status:10s} {name:60s} {color:30s} {quantity:5d}"
    print("{i:4s} {status:10s} {name:60s} {color:30s} {quantity:5s}".format(
        i="i", status="status", name="name", color="color", quantity="qty"))
    print((4 + 1 + 10 + 1 + 60 + 1 + 30 + 1 + 5) * "-")

    # load half-complete price guide if available
    if args_.resume:
        old_parts = io.load_price_guide(open(args_.resume))
        old_parts = utils.groupby(old_parts, lambda x: (x['item_id'], x['wanted_color_id']))
    else:
        old_parts = {}

    available_parts = []

    # for each wanted lot
    for (i, item) in enumerate(wanted_parts):
        # skip this item if we already have enough
        matching = old_parts.get((item['ItemID'], item['ColorID']), [])
        quantity_found = sum(e['quantity_available'] for e in matching)

        print(fmt.format(i=i, status="seeking", name=item['ItemName'], color=item['ColorName'], quantity=item['Qty']))

        if quantity_found >= item['Qty']:
            colors = [color.name(c_id) for c_id in set(e['color_id'] for e in matching)]
            print(fmt.format(i=i, status="passing", name=item['ItemName'], color=",".join(colors),
                             quantity=quantity_found))
            available_parts.extend(matching)
        else:
            try:
                # fetch price data for this item in the closest available color
                new = scraper.price_guide(item, max_cost_quantile=args_.max_price_quantile)
                available_parts.extend(new)

                # print out status message
                total_quantity = sum(e['quantity_available'] for e in new)
                colors = [color.name(c_id) for c_id in set(e['color_id'] for e in new)]
                print(fmt.format(i=i, status="found", name=item['ItemName'], color=",".join(colors),
                                 quantity=total_quantity))

                if total_quantity < item['Qty']:
                    print('WARNING! Couldn\'t find enough parts!')

            except Exception as e:
                print('Catastrophic Failure! :(')
                traceback.print_exc()

    # save price data
    io.save_price_guide(open(args_.output, 'w'), available_parts)


def minimize(args_):
    """Minimize the cost of a purchase"""
    # ------------ Loading ------------
    # load in wanted parts lists
    if args_.parts_list.endswith(".bsx"):
        wanted_parts = io.load_bsx(open(args_.parts_list))
    else:
        wanted_parts = io.load_xml(open(args_.parts_list))
    print('Loaded %d different parts' % len(wanted_parts))

    # load in pricing data
    available_parts = io.load_price_guide(open(args_.price_guide))
    n_available = len(available_parts)
    n_stores = len(set(e['store_id'] for e in available_parts))
    print('Loaded %d available lots from %d stores' % (n_available, n_stores))

    # load in store metadata
    if args_.store_list is not None:
        store_metadata = io.load_store_metadata(open(args_.store_list))
        print('Loaded metadata for %d stores' % len(store_metadata))

        # ------- Filtering Stores ------------
        # select which stores to get parts from
        allowed_stores = list(store_metadata)
        if args_.source_country is not None:
            print('Only allowing stores from %s' % (args_.source_country,))
            allowed_stores = [x for x in allowed_stores if x['country_name'] == args_.source_country]

        if args_.target_country is not None:
            print('Only allowing stores that ship to %s' % (args_.target_country,))
            allowed_stores = [s for s in allowed_stores
                              if args_.target_country in s['ships']
                              or (len(s['ships']) == 1 and s['ships'][0] == 'All Countries WorldWide')]

        if args_.feedback is not None and args_.feedback > 0:
            print('Only allowing stores with feedback >= %d' % (args_.feedback,))
            allowed_stores = [x for x in allowed_stores if x['feedback'] >= args_.feedback]

        if args_.exclude is not None:
            excludes = set(args_.exclude.strip().split(","))
            excludes = [int(x) for x in excludes]
            print('Forcing exclusion of: %s' % (excludes,))
            allowed_stores = [x for x in allowed_stores if not (x['store_id'] in excludes)]

        store_ids = [x['store_id'] for x in allowed_stores]
        store_ids = list(set(store_ids))
        print('Using %d stores' % len(store_ids))

        available_parts = [x for x in available_parts if x['store_id'] in store_ids]

        solution = minimizer.greedy(wanted_parts, available_parts)[0]
        if not minimizer.is_valid_solution(wanted_parts, solution['allocation']):
            print(("You're too restrictive. There's no way to buy what " +
                   "you want with these stores"))
            sys.exit(1)

    # -------------- Minimization --------------
    if args_.algorithm in ['ilp', 'greedy']:
        if args_.algorithm == 'ilp':
            # Integer Linear Programming
            solution = minimizer.gurobi(
                wanted_parts,
                available_parts,
                allowed_stores,
                shipping_cost=args_.shipping_cost
            )[0]
            assert minimizer.is_valid_solution(wanted_parts, solution['allocation'], allowed_stores)
        elif args_.algorithm == 'greedy':
            # ---- Greedy Set Cover ----
            solution = minimizer.greedy(wanted_parts, available_parts)[0]

        # check and save
        io.save_solution(open(args_.output + ".json", 'w'), solution)

        # print outs
        stores = set(e['store_id'] for e in solution['allocation'])
        cost = solution['cost']
        unsatisified = minimizer.unsatisified(wanted_parts, solution['allocation'])
        print('Total cost: $%.2f | n_stores: %d | remaining lots: %d' % (cost, len(stores), len(unsatisified)))

    elif args_.algorithm == 'brute-force':
        # for each possible number of stores
        for k in range(1, args_.max_n_stores):
            # find all possible solutions using k stores
            solutions = minimizer.brute_force(wanted_parts, available_parts, k)
            solutions = list(sorted(solutions, key=lambda x: x['cost']))
            solutions = solutions[0:10]

            # save output
            output_folder = os.path.join(args_.output, str(k))
            try:
                os.makedirs(output_folder)
            except OSError:
                pass

            for (i, solution) in enumerate(solutions):
                output_path = os.path.join(output_folder, "%02d.json" % i)
                with open(output_path, 'w') as f:
                    io.save_solution(f, solution)

            # print outs
            if len(solutions) > 0:
                print('%8s %40s' % ('Cost', 'Store IDs'))
                for sol in solutions:
                    print('$%7.2f %40s' % (sol['cost'], ",".join(str(s) for s in sol['store_ids'])))
            else:
                print("No solutions using %d stores" % k)


def wanted_list(args_):
    """Create BrickLink Wanted Lists for each store"""
    # load recommendation
    recommendation = io.load_solution(open(args_.recommendation))
    store_metadata = io.load_store_metadata(open(args_.store_list))
    io.save_xml_per_vendor(args_.output, recommendation, store_metadata)


def store_list(args_):
    """Get metadata for stores"""
    info = scraper.store_info(country=args_.country)
    io.save_store_metadata(open(args_.output, 'w'), info)


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Brickrake: the BrickLink Store Recommendation Engine")
    subparsers = parser.add_subparsers()

    parser_pg = subparsers.add_parser("price_guide",
                                      help="Download pricing information from BrickLink")
    parser_pg.add_argument('--parts-list', required=True,
                           help='BSX file containing desired parts')
    parser_pg.add_argument('--max-price-quantile', default=1.0, type=float,
                           help=('Ignore lots that cost more than this quantile' +
                                 ' of the price distribution per item'))
    parser_pg.add_argument('--resume', default=None,
                           help='Resume a previously run price_guide search')
    parser_pg.add_argument('--output', required=True,
                           help='Location to save price guide for wanted list')
    parser_pg.set_defaults(func=price_guide)

    parser_mn = subparsers.add_parser("minimize",
                                      help="Find a small set of vendors to buy parts from")
    parser_mn.add_argument('--parts-list', required=True,
                           help='BSX file containing desired parts')
    parser_mn.add_argument('--price-guide', required=True,
                           help='Pricing information output by "brickrake price_guide"')
    parser_mn.add_argument('--store-list', default=None,
                           help='JSON file containing store metadata. If using algorithm=ilp, this is required')
    parser_mn.add_argument('--source-country', default=None,
                           help='limit search to stores in a particular country')
    parser_mn.add_argument('--target-country', default=None,
                           help='limit search to stores that ship to a particular country')
    parser_mn.add_argument('--feedback', default=0, type=int,
                           help='limit search to stores with enough feedback')
    parser_mn.add_argument('--exclude', default=None,
                           help='Force exclusion of the following comma-separated store IDs')
    parser_mn.add_argument('--algorithm', default='ilp',
                           choices=['ilp', 'brute-force', 'greedy'],
                           help='Algorithm used to select vendors')
    parser_mn.add_argument('--max-n-stores', default=5, type=int,
                           help=('Maximum number of different stores in a proposed solution.' +
                                 'Only used if algorithm=brute-force.'))
    parser_mn.add_argument('--shipping-cost', default=10.0, type=float,
                           help=('Estimated cost of shipping per store. ' +
                                 'Only used if algorithm=ilp'))
    parser_mn.add_argument('--output', required=True,
                           help='Directory to save purchase recommendations')
    parser_mn.set_defaults(func=minimize)

    parser_wl = subparsers.add_parser("wanted_list",
                                      help="Create a BrickLink Wanted List")
    parser_wl.add_argument("--recommendation", required=True,
                           help='JSON file output by "brickrake minimize"')
    parser_wl.add_argument('--store-list', required=True,
                           help='JSON file containing store metadata.')
    parser_wl.add_argument("--output", required=True,
                           help="Folder to create BrickLink Wanted List XML in")
    parser_wl.set_defaults(func=wanted_list)

    parser_st = subparsers.add_parser("stores",
                                      help="Download metadata about stores")
    parser_st.add_argument("--country", default=None,
                           help="Only gather metadata for stores from this country")
    parser_st.add_argument("--output", required=True,
                           help="Folder to create BrickLink Wanted List XML in")
    parser_st.set_defaults(func=store_list)

    args = parser.parse_args()
    args.func(args)
