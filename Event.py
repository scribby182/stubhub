import datetime
import re
import os
import numpy as np
from pprint import pprint
import json
from Seats import DuplicateSeatError, SeatGroupError, SeatGroupChronology, SeatGroup, Seat, SeatGroupFixedPrice, dt_list_arange, dt_list_trim
from stubhub_list_scrape import DATETIME_FORMAT
from itertools import product
import matplotlib.pyplot as plt

class Event(object):
    """
    Object for a event such as a game or concert.
    """
    def __init__(self):
        self.chronology = SeatGroupChronology()
        self.datetime = None
        self.location = None
        self.meta = None # For things like home/away team, etc.
        self.sales = None
        self.added = None
        self.new_price = None
        self.new_listid = None
        self.namemap = [] # For holding any common seat name remapping.  See subclasses below for example
        self.ignore = [] # List of location tuples that are to be ignored during any seat import
        self.include = None # List of locations that will be used (if not None, anything not on this list is removed after loading SGC)
        self.season_ticket_groups = {}
        self.season_tickets = SeatGroup()


    def add_meta(self, json_file):
        """
        Add an Event's metadata from a JSON formatted event file.
        :param json_file:
        :return:
        """
        # Should there be a non-JSON way to do this too?  Maybe this is dict based and then the JSON one loads and
        # formats to a standard dict?
        raise NotImplementedError()

    def add_timepoint(self, timepoint, json_file, update_names=True, update_meta=True):
        """
        Add a SeatGroup timepoint to the event's chronology from a JSON formatted event file, identified by a timepoint

        Possible improvement: Could update sales/add_seat/... Chronologies for each seatgroup added.
        Could run prev_diff = diff(this_timepoint, prev), next_diff = diff(next_timepoint, this_timepoint), then
        sales.add_seat(prev_diff, this_timepoint), sales.remove(next_diff), and sales.add_seat(next_diff, next_timepoint).
        Probably want this auto_update togglable, and group-adds could disable to avoid remaking sales infor that gets
        rewritten immediately afterwards.


        :param timepoint: A datetime object (used as the key to identify the timepoint)
        :param json_file: Filename of a JSON file with event listings data
        :param update_names: If true, invoke
        :return: None
        """
        self.chronology.add_seatgroup_from_event_json(timepoint, json_file, update_names=self.namemap)
        # Remove any seats on ignore list
        # Better way to do this?  Feels wasteful.
        for ig in self.ignore:
            try:
                self.chronology.seatgroups[timepoint].remove(ig, remove_deep_seats=True, cleanup_empty_groups=True)
            except SeatGroupError:
                pass

        if update_meta:
            if self.meta != None and self.meta != self.chronology.seatgroups[timepoint].meta:
                print("WARNING: New timepoint metadata '{0}' does not match past metadata '{1}' - updating to newest metadata".format(self.chronology.seatgroups[timepoint].meta, self.meta))
            self.meta = self.chronology.seatgroups[timepoint].meta


    def init_season_ticket_groups(self):
        """
        Prototype function for initializing season_ticket_groups in subclasses
        :return: None
        """
        raise NotImplementedError()


    def init_season_ticket_seatgroup(self, price_override=None):
        """
        Initialize a SeatGroup with all season tickets.

        Optionally initialize all seats to a fixed price (for debugging)

        :param price_override: A fixed price for a single game for all seats (useful for debugging).  If None, standard prices are used
        :return: None
        """
        for group in self.season_ticket_groups:
            sgfp = SeatGroupFixedPrice()
            if price_override is None:
                this_price = self.season_ticket_groups[group]['price']
            else:
                this_price = price_override
            sgfp.add_seat(Seat(this_price, season_ticket_group=group))
            for s in self.season_ticket_groups[group]['locs']:
                self.season_tickets.add_seat(sgfp, s)


    def scrape_timepoints_from_dir(self, eventid, directory, update_names=True, tp_slice=None):
        """
        Scrapes directory for JSON listings files of format "eventid_YYYY-MM-DD_hh-mm-ss.json" and adds them to event.

        :param eventid: EventID to look for in directory (only adds events with this ID)
        :param directory: Directory to search for listing files
        :param tp_slice: Optionally load only some of the data, based on a date slice
                      If None, all data files associated with event are loaded.
                      If a slice object, data is loaded from start to end in step intervals:
                        start: datetime object setting the start of the date interval to load
                        stop: datetime object setting the end of the date interval to load
                        step: timedelta object setting the interval of the data to load
                      At least start and one of stop and step are required:
                        start + stop: all data from start to stop is loaded
                        start + step: data is loaded in step increments from start to the end of data
                        start + stop + step: data is loaded from start to stop in step increments
                      Notes:
                        - step can be negative so long as stop==None or stop<start (useful for loading from a set date
                        backward)
                        - In practice, step will load data at approximately the interval requested, as data points for
                        the exact dates requested will not be available.  This can result in some gaps in timelines
                        because more than one step may be closest to the same data file and that data file will only
                        be loaded once
        :return: None
        """

        def parse_listings_fn(fn):
            match = re.match(r'(\d+)_(.+)\.json', fn)
            eventid = int(match.group(1))
            timepoint = datetime.datetime.strptime(match.group(2), DATETIME_FORMAT)
            return (eventid, timepoint)

        # Get all filenames in the directory, parse them into (eventid, datetime), then add those that match the
        # requested eventID to the Event
        tp_map = {}
        for fn in os.listdir(directory):
            full_fn = os.path.join(directory, fn)
            if os.path.isfile(full_fn):
                try:
                    this_id, this_time = parse_listings_fn(fn)
                except:
                    print(
                        "DEBUG: WARNING: {0} cannot be parsed into listings filename format - skipping".format(fn))
                    continue
                if this_id == eventid:
                    tp_map[this_time] = full_fn
                    # self.add_timepoint(this_time, full_fn, update_names=update_names)
                else:
                    print("DEBUG: {0} is not part of event {1} - skipping".format(fn, eventid))
            else:
                print("DEBUG: {0} is not a file".format(fn))

        if tp_slice:
            print("Performing sparse data load")
            tp_list = sorted(list(tp_map.keys()))
            if tp_slice.step is None:
                # Load all data within a range
                tp_list = dt_list_trim(tp_list, tp_slice)
            else:
                # Sparsely load data in a range
                tp_list = dt_list_arange(tp_list, tp_slice)
            tp_map = {tp: tp_map[tp] for tp in tp_list}
            print("Loading only {0} timepoints:".format(len(tp_map)))
            pprint(sorted(tp_map.keys()))

        # Actually load the data in tp_map
        for tp, fn in tp_map.items():
            self.add_timepoint(tp, fn, update_names=update_names)

        # Keep only the locations on the include list
        if self.include is not None:
            self.chronology = self.chronology.get_seats(self.include)


    def infer_chronological_changes(self):
        diff = self.chronology.find_differences()
        self.sales = diff['removed']
        self.added = diff['added']
        self.new_price = diff['new_price']
        self.new_listid = diff['new_listid']
        self.sales_relative = self.sales - self.season_tickets
    # Properties
    # Add day_of_week property?
    # Add time of event/date of event, which pulls from the self.datetime?


    def plot_price_history(self, groups='all', price_type='rel', prefix="", plot_date_relative_to_event=True, ymin=-200.0, ymax=500.0, ):
        """
        Plot price versus time for the event by season ticket groups, (DISABLED: filtering prices by function f).

        :param price_type: rel for relative prices, abs for absolute
        :param f: (DISABLED) Same format as f in SGC.get_prices()
        :param plot_date_relative_to_event: False: Plot dates as stored in SGC
                                True: Plot dates relative to the event's data in self.meta (eg: Event-1 day, -2 days...)
                                A timepoint: Plot dates relative to the specified timepoint
        :return: None
        """
        if price_type == 'rel':
            sgc = self.sales_relative
        elif price_type == 'abs':
            sgc = self.sales
        else:
            raise ValueError("Invalid price_type '{0}' - must be 'abs' or 'rel'".format(price_type))

        if groups == 'all':
            groups = sorted(self.season_ticket_groups)

        plt.style.use('ggplot')
        for i, g in enumerate(groups):
            # NEED BETTER HANDLING OF GROUPS THAT ARE EMPTY
            try:
                fig, ax = plt.subplots()
                sales_rel = (sgc.get_seats(self.season_ticket_groups[g]['locs']) - self.season_tickets).get_prices()
                sales_all_rel = (sgc.get_seats(self.season_ticket_groups[g]['locs']) - self.season_tickets).get_prices(f=None)

                if plot_date_relative_to_event is False:
                    dates = sales_rel['timepoint']
                    dates_all = sales_all_rel['timepoint']
                    line = ax.plot_date(dates, sales_rel['price'], "-", label=g)[0]
                    ax.plot_date(dates_all, sales_all_rel['price'], ".", color=line.get_color())
                    fig.autofmt_xdate()

                elif plot_date_relative_to_event:
                    if plot_date_relative_to_event is True:
                        plot_date_relative_to_event = self.meta['date']
                    elif not isinstance(plot_date_relative_to_event, datetime.datetime):
                        raise ValueError("normalize_dates must be True, False, or a datetime object")
                    # Is this better served as a SGC property, or at least method?  Will it get used elsewhere?
                    dates = [(d - plot_date_relative_to_event).total_seconds() / 86400.0 for d in sales_rel['timepoint']]
                    dates_all = [(d - plot_date_relative_to_event).total_seconds() / 86400.0 for d in sales_all_rel['timepoint']]
                    line = ax.plot(dates, sales_rel['price'], "-", label=g)[0]
                    ax.plot(dates_all, sales_all_rel['price'], ".", color=line.get_color())
                    fig.autofmt_xdate()
                    ax.set_xlabel("Days Before Event")
                    ax.set_xlim((None, 0))

                ax.set_ylim((ymin, ymax))
                ax.set_ylabel("Sale Price Relative to Season Ticket Price (${0})".format(self.season_ticket_groups[g]['price']))
                plt.legend(loc='upper left', fontsize='x-small')
                fig.savefig(prefix + g + ".png")
            except Exception as e:
                print("LIKELY EXCEPTION DUE TO EMPTY GROUPS - NEED TO IMPROVE THIS")
                print(e)

    def normalize_chronology(self, dt_slice):
        """
        Convert the internal Chronology into one with timepoints ranging from start to stop at step intervals using SGC.arange

        See SGC.arange for more detail on syntax
        :param start: Default: self.meta['date']
        :param stop: Default: None (continue stepping until past the first timepoint)
        :param step: Default: -6 hours
        :return:
        """
        if dt_slice.start is None:
            start = self.meta['date']
        else:
            start = dt_slice.start
        if dt_slice.step is None:
            step = datetime.timedelta(hours=-6)
        else:
            step = dt_slice.step
        # Update thje slice with defaults
        dt_slice = slice(start, dt_slice.stop, step)
        # self.chronology = self.chronology.arange(start, stop, step, rename_timepoints=rename_timepoints)
        self.chronology = self.chronology[dt_slice]

class Panthers(Event):
    # TODO: This catches most bad names, but a few like "Gridiron" and "side" (from "lower side") still slip through.  Add a "remove seats like this" feature?
    def __init__(self, price=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.namemap = [
            (r'(?i)\s*Club\s*', ''),
            (r'(?i)\s*I+\s+', ''),
            (r'(?i)\s*Terrace\s*', ''),
            (r'(?i)\s*lower\s*', ''),
            (r'(?i)\s*middle\s*', ''),
            (r'(?i)\s*upper\s*', ''),
            (r'(?i)\s*end zone\s*', ''),
            (r'(?i)\s*premium\s*', ''),
            (r'(?i)\s*sideline\s*', ''),
        ]

        # Custom ignore list (these sections have no associated season ticket price, so no need of them)
        self.ignore = [(105,), (118,), (125,), (138,), ("Gridiron", )]

        # Build season tickets
        self.init_season_ticket_groups()
        self.init_season_ticket_seatgroup(price_override=price)

        # Custom inclusion list (only sections in this list are loaded)
        self.include = set()
        for s in self.season_ticket_groups:
            self.include.update(self.season_ticket_groups[s]['locs'])

    def init_season_ticket_groups(self):
        """
        Initializes season ticket groupings for a Panthers event.

        :return: None
        """
        # Season Ticket Section Data
        rows_box = ["WC"] + \
                   ["1{0}".format(c) for c in "ABCDEFGHIJ"] + \
                   list(range(1, 17))
        rows_reserved = list(range(17, 60))

        # Club 1
        sections = [315, 316, 343, 344]
        self.season_ticket_groups['Club 1'] = {
			'locs': list(product(sections)),
			'price': 4500.0 / 8.0,
		}

        # Club 2
        sections = [313, 314, 317, 318, 341, 342, 345, 346]
        self.season_ticket_groups['Club 2'] = {
			'locs': list(product(sections)),
			'price': 3250.0 / 8.0,
		}

        # Club 3
        sections = [308, 309, 310, 311, 312, 319, 320, 321, 322, 323, 336, 337, 338, 339, 340, 347, 348, 349, 350]
        self.season_ticket_groups['Club 3'] = {
			'locs': list(product(sections)),
			'price': 2750.0 / 8.0,
		}

        # A1
        sections = [111, 112, 131, 132]
        self.season_ticket_groups['A1'] = {
			'locs': list(product(sections)),
			'price': 1950.0 / 8.0,
		}

        # A2
        sections = [110, 113, 130, 133]
        self.season_ticket_groups['A2'] = {
			'locs': list(product(sections)),
			'price': 1600.0 / 8.0,
		}

        # B
        sections = [106, 107, 108, 109, 114, 115, 116, 117, 126, 127, 128, 129, 134, 135, 136, 137]
        self.season_ticket_groups['B'] = {
			'locs': list(product(sections)),
			'price': 1300.0 / 8.0,
		}

        # C
        sections = [101, 102, 103, 104, 119, 120, 121, 122, 123, 124, 139, 140, 201, 202, 203, 204, 205, 206, 224, 225, 226, 227,
                    228, 229, 230, 231, 232, 233, 234, 252, 253, 254, 255, 256]
        self.season_ticket_groups['C'] = {
			'locs': list(product(sections)),
			'price': 1100.0 / 8.0,
		}

        # D Box
        sections = [513, 514, 515, 516, 540, 541, 542, 543]
        rows = rows_box
        self.season_ticket_groups['D Box'] = {
			'locs': list(product(sections, rows)),
			'price': 840.0 / 8.0,
		}

        # D Reserved
        # sections = [513, 514, 515, 516, 540, 541, 542, 543]
        rows = rows_reserved
        self.season_ticket_groups['D Reserved'] = {
			'locs': list(product(sections, rows)),
			'price': 710.0 / 8.0,
		}

        # E Box
        sections = list(range(508, 513)) + list(range(517, 522)) + list(range(535, 540)) + list(range(544, 549))
        rows = rows_box
        self.season_ticket_groups['E Box'] = {
			'locs': list(product(sections, rows)),
			'price': 740.0 / 8.0,
		}

        # E Reserved
        # sections =
        rows = rows_reserved
        self.season_ticket_groups['E Reserved'] = {
			'locs': list(product(sections, rows)),
			'price': 610.0 / 8.0,
		}

        # F Box
        sections = [501, 502, 503] + list(range(526, 531)) + [553, 554]
        rows = rows_box
        self.season_ticket_groups['F Box'] = {
			'locs': list(product(sections, rows)),
			'price': 680.0 / 8.0,
		}

        # F Reserved
        # sections =
        rows = rows_reserved
        self.season_ticket_groups['F Reserved'] = {
			'locs': list(product(sections, rows)),
			'price': 550.0 / 8.0,
		}

        # G Box
        sections = [505, 506, 523, 524, 532, 533, 550, 551]
        rows = rows_box
        self.season_ticket_groups['G Box'] = {
			'locs': list(product(sections, rows)),
			'price': 610.0 / 8.0,
		}

        # G Reserved
        # sections =
        rows = rows_reserved
        self.season_ticket_groups['G Reserved'] = {
			'locs': list(product(sections, rows)),
			'price': 480.0 / 8.0,
		}

        # X Box
        sections = [507, 522, 534, 549]
        rows = rows_box
        self.season_ticket_groups['X Box'] = {
			'locs': list(product(sections, rows)),
			'price': 740.0 / 8.0,
		}

        # X Reserved
        # sections =
        rows = rows_reserved
        self.season_ticket_groups['X Reserved'] = {
			'locs': list(product(sections, rows)),
			'price': 610.0 / 8.0,
		}

        # Y Box
        sections = [504, 525, 531, 552]
        rows = rows_box
        self.season_ticket_groups['Y Box'] = {
			'locs': list(product(sections, rows)),
			'price': 680.0 / 8.0,
		}

        # Y Reserved
        # sections =
        rows = rows_reserved
        self.season_ticket_groups['Y Reserved'] = {
            'locs': list(product(sections, rows)),
            'price': 550.0 / 8.0,
        }

        # # Unknown - these are not part of any set section
        # sections = [105, 118, 125, 138]
        # self.season_ticket_groups['Unknown'] = {
        #     'locs': list(product(sections)),
        #     'price': 5000.0, # Set these to a high ticket price so they never come up as super good deals
        # }


# Exceptions
class EventError(Exception):
    pass

# Helper
def mygen(start=0, stop=100, inc=1):
    """A simple custom generator"""
    i = start
    while i < stop:
        yield i
        i += inc