import datetime
import re
import os
import numpy as np
from pprint import pprint
import json
import copy
from Seats import SeatGroupChronology, SeatGroup, Seat, SeatGroupFixedPrice, dt_list_arange, dt_list_trim
from Seats import DuplicateSeatError, SeatGroupError, EmptySeatGroupError
from Seats import np_describe
from stubhub_list_scrape import DATETIME_FORMAT
from itertools import product
import matplotlib.pyplot as plt
import pandas as pd


class Event(object):
    """
    Object for a event such as a game or concert.
    """
    def __init__(self, eventid=None):
        self.chronology = SeatGroupChronology()
        self.eventid = eventid
        self.event_info_file = None
        self.datetime = None
        self.opponent = None
        self.sales = None
        self.added = None
        self.new_price = None
        self.new_listid = None
        self.namemap = [] # For holding any common seat name remapping.  See subclasses below for example
        self.ignore = [] # List of location tuples that are to be ignored during any seat import
        self.include = None # List of locations that will be used (if not None, anything not on this list is removed after loading SGC)
        self.season_ticket_groups = {}
        self.season_tickets = SeatGroup()

        self.sales_filter_settings = {
            'avail_tick_thresh_max_ratio': 1.5,  # Maximum ratio someone will pay above the cheapest available ticket
            'avail_tick_thresh_min_abs': 30, # max_ratio above avail not applied if the absolute delta is less than this
            'avail_tick_rule_min_seats': 5, # max_ratio above available not applied if available seats < this
            'st_max_ratio': 5, # Maximum sales price to season ticket ratio
            'st_max_abs': 750, # Maximum sales price to season ticket delta

        }

        # Set default averages that will be calculated when specific averages are not specified
        self.default_averages_to_calculate = [
                              ## 'sales_min_average',
                              ## 'listed_min_average',
                              ## 'sales_filtered_average',
                              ## 'listed_filtered_average',
                              ## 'sales_average',
                              ## 'listed_average',
                              # 'sales_min_moving_average',
                              ## 'listed_min_moving_average',
                              'sales_filtered_moving_average',
                              ## 'listed_filtered_moving_average',
                              # 'sales_moving_average',
                              ## 'listed_moving_average',
                              'sales_filtered_min_moving_average',
                              ]

        self.sales_min_average = None
        self.listed_min_average = None
        self.sales_filtered_average = None
        self.listed_filtered_average = None
        self.sales_average = None
        self.listed_average = None

        self.sales_min_moving_average = None
        self.listed_min_moving_average = None
        self.sales_filtered_min_moving_average = None
        self.sales_filtered_moving_average = None
        self.listed_filtered_moving_average = None
        self.sales_moving_average = None
        self.listed_moving_average = None

        self.sales_min_average_rel = None
        self.listed_min_average_rel = None
        self.sales_filtered_average_rel = None
        self.listed_filtered_average_rel = None
        self.sales_average_rel = None
        self.listed_average_rel = None

        self.sales_min_moving_average_rel = None
        self.listed_min_moving_average_rel = None
        self.sales_filtered_min_moving_average_rel = None
        self.sales_filtered_moving_average_rel = None
        self.listed_filtered_moving_average_rel = None
        self.sales_moving_average_rel = None
        self.listed_moving_average_rel = None

    def add_meta(self, json_file=None):
        """
        Add an Event's metadata from a JSON formatted event info file, looking it up by eventid.

        :param json_file:
        :return: None
        """
        if json_file is None:
            json_file = self.event_info_file
        with open(json_file, 'r') as f:
            event_meta = json.load(f)
        try:
            event_meta[self.eventid]
            eid = self.eventid
        except KeyError:
            # JSON dump writes keys as strings
            event_meta[str(self.eventid)]
            eid = str(self.eventid)

        self.opponent = event_meta[eid]['away']
        self.datetime = datetime.datetime.strptime(event_meta[eid]['date'], DATETIME_FORMAT)


    def add_timepoint(self, timepoint, json_file, update_names=True, update_meta=False):
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


    def scrape_timepoints_from_dir(self, directory="./", update_names=True, tp_slice=None, tp_map=None):
        """
        Scrapes directory for JSON listings files of format "eventid_YYYY-MM-DD_hh-mm-ss.json" and adds them to event.

        :param eventid: DEPRECIATED EventID to look for in directory (only adds events with this ID)
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
        :param tp_map: a dictionary of timepoints and their corresponding files.  If specified, directory is not
                       searched and instead only these files are investigated.  Note that tp_slice can still reduce this
                       set of files based on slicing rules
        :return: None
        """
        # Get all filenames in the directory, parse them into (eventid, datetime), then add those that match the
        # requested eventID to the Event
        if tp_map is None:
            tp_map = find_listings_files(directory)[self.eventid]

        if tp_slice:
            print("Performing sparse data load")
            tp_list = sorted(list(tp_map.keys()))
            total_tp = len(tp_list)
            if tp_slice.step is None:
                # Load all data within a range
                tp_list = dt_list_trim(tp_list, tp_slice)
            else:
                # Sparsely load data in a range
                tp_list = dt_list_arange(tp_list, tp_slice)
            tp_map = {tp: tp_map[tp] for tp in tp_list}
            print("Loading only {0} of {1} timepoints:".format(len(tp_map), total_tp))

        # Actually load the data in tp_map
        # Loading in sorted order isn't required, but makes debugging easier and doesn't cost much...
        for tp, fn in sorted(tp_map.items()):
            self.add_timepoint(tp, fn, update_names=update_names)

        # Keep only the locations on the include list
        if self.include is not None:
            old_locs = self.chronology.get_locs()
            self.chronology = self.chronology.get_seats(self.include)
            new_locs = self.chronology.get_locs()
            removed = [loc for loc in old_locs if loc not in new_locs]
            # print("Include filtered out {0} seats:".format(len(removed)))
            # pprint(removed)

    def infer_chronological_changes(self):
        self.chronology.find_differences()
        self.sales = self.chronology.sales
        self.added = self.chronology.added
        self.new_price = self.chronology.new_price
        self.new_listid = self.chronology.new_listid

        # Filter "sales" to remove any abnormal data:
        #   (Settings pulled from self.sales_filter_settings)
        #   1)  Assume nobody will ever pay more than st_max_ratio * Season Ticket Price
        #   2)  Assume nobody will ever pay more than st_max_abs above Season Ticket Price
        #   3)  Assume nobody will pay more than avail_tick_thresh_ratio * min(all available tickets in season ticket group)
        #       Ignore this rule if (Sale price - Season Ticket Price < avail_tick_thresh_min_abs)
        #       Ignore this rule if minimum available tickets in group < avail_tick_min
        avail_tick_thresh_max_ratio = self.sales_filter_settings['avail_tick_thresh_max_ratio']
        avail_tick_thresh_min_abs = self.sales_filter_settings['avail_tick_thresh_min_abs']
        avail_tick_rule_min_seats = self.sales_filter_settings['avail_tick_rule_min_seats']
        st_max_ratio = self.sales_filter_settings['st_max_ratio']
        st_max_abs = self.sales_filter_settings['st_max_abs']

        # Apply filters
        sales_filt = copy.deepcopy(self.sales) # faster way?  Make a real copy routine?
        # print("Number of seats in sales before filter: {0}".format(len(sales_filt)))
        for g in sorted(self.season_ticket_groups): # Sorting not necessary, but easier for debugging
            st_price = self.season_ticket_groups[g]['price']
            locs = self.season_ticket_groups[g]['locs']
            group_sales_sgc = self.sales.get_seats(seat_locs=locs)
            for i_tp in range(len(group_sales_sgc.sorted_timepoints)):
                tp = group_sales_sgc.sorted_timepoints[i_tp]
                tp_sales_sg = group_sales_sgc.seatgroups[tp]
                # Check if there's anything to filter
                if len(tp_sales_sg) == 0:
                    # print("No sales in this group at this timepoint - moving to next timepoint")
                    continue

                # Collect the data
                tp_avail = self.chronology.seatgroups[tp].get_seats_as_seatgroup(seat_locs=locs, fail_if_missing=False)
                tp_prices = tp_sales_sg.get_prices()
                tp_prices_masks = []
                # Make the filters (True means a row will be removed)
                # Filter 1) st_max_ratio
                tp_prices_masks.append(tp_prices > st_max_ratio * st_price)

                # Filter 2) st_max_abs
                tp_prices_masks.append(tp_prices - st_price > st_max_abs)

                # Filter 3) Ratio to min avail ticket
                if len(tp_avail) >= avail_tick_rule_min_seats:
                    tp_avail_min = tp_avail.get_prices().min()
                    tp_prices_masks.append((tp_prices > avail_tick_thresh_max_ratio * tp_avail_min) & (tp_prices - tp_avail_min > avail_tick_thresh_min_abs))

                # Combine filters (if any available)
                if len(tp_prices_masks) > 0:
                    tp_prices_mask = np.any(tp_prices_masks, axis=0)

                    # print("Mask summary (last column is combination):")
                    # pprint(np.stack([*tp_prices_masks, tp_prices_mask], axis=1))

                    if any(tp_prices_mask):
                        to_filter = [loc for i, loc in enumerate(tp_sales_sg.get_locs()) if tp_prices_mask[i]] # probably a better way avail...
                        # to_filter = np.array(tp_sales_sg.get_locs())[tp_prices_mask]
                        # print("SG of to_filter (just for debugging)")
                        # to_filter_sg = tp_sales_sg.get_seats_as_seatgroup(seat_locs = to_filter) # DEBUG
                        # to_filter_sg.display() # DEBUG
                        for seat in to_filter:
                            sales_filt.seatgroups[tp].remove(seat)
                # print("Number of seats in sales after partial filter: {0}".format(len(sales_filt)))
                # else:
                #     print("Did not find any seats to filter")
        # print("Number of seats in sales after filter: {0}".format(len(sales_filt)))

        self.sales_filtered = sales_filt

        # Calculate sales prices relative to season ticket costs
        self.sales_rel = self.sales - self.season_tickets
        self.sales_filtered_rel = self.sales_filtered - self.season_tickets

    # Properties
    # Add day_of_week property?
    # Add time of event/date of event, which pulls from the self.datetime?

    def calc_all_average_price_history(self, averages_to_calculate = None):
        """
        Calculate and store standard average price history data.

        :return: None
        """

        if averages_to_calculate is None:
            averages_to_calculate = self.default_averages_to_calculate

        moving_average_timedelta = datetime.timedelta(days=5)

        # Settings for different types of averages
        settings = {
            'sales_min_average': {
                                  'average_type': 'cumulative',
                                  'price_type': 'sales',
                                  'filter_func': np.min,
                                  'moving_average_timedelta': moving_average_timedelta,
                                  },
            'listed_min_average': {
                                   'average_type': 'cumulative',
                                   'price_type': 'listed',
                                   'filter_func': np.min,
                                   'moving_average_timedelta': moving_average_timedelta,
                                   },
            'sales_filtered_average': {
                                       'average_type': 'cumulative',
                                       'price_type': 'sales_filtered',
                                       'filter_func': None,
                                       'moving_average_timedelta': moving_average_timedelta,
                                       },
            'sales_average': {
                              'average_type': 'cumulative',
                              'price_type': 'sales',
                              'filter_func': None,
                              'moving_average_timedelta': moving_average_timedelta,
                              },
            'listed_average': {
                               'average_type': 'cumulative',
                               'price_type': 'listed',
                               'filter_func': None,
                               'moving_average_timedelta': moving_average_timedelta,
                               },
            'sales_min_moving_average': {
                                         'average_type': 'moving',
                                         'price_type': 'sales',
                                         'filter_func': np.min,
                                         'moving_average_timedelta': moving_average_timedelta,
                                         },
            'listed_min_moving_average': {
                                          'average_type': 'moving',
                                          'price_type': 'listed',
                                          'filter_func': np.min,
                                          'moving_average_timedelta': moving_average_timedelta,
                                          },
            'sales_filtered_moving_average': {
                                              'average_type': 'moving',
                                              'price_type': 'sales_filtered',
                                              'filter_func': None,
                                              'moving_average_timedelta': moving_average_timedelta,
                                              },
            'sales_moving_average': {
                                     'average_type': 'moving',
                                     'price_type': 'sales',
                                     'filter_func': None,
                                     'moving_average_timedelta': moving_average_timedelta,
                                     },
            'listed_moving_average': {
                                      'average_type': 'moving',
                                      'price_type': 'listed',
                                      'filter_func': None,
                                      'moving_average_timedelta': moving_average_timedelta,
                                      },
            'sales_filtered_min_moving_average': {
                                                  'average_type': 'moving',
                                                  'price_type': 'sales_filtered',
                                                  'filter_func': np.min,
                                                  'moving_average_timedelta': moving_average_timedelta,
                                                  },
        }

        # Initialize the attributes we need
        for p in averages_to_calculate:
            setattr(self, p, {})
            setattr(self, p + "_rel", {})

        caph = self.average_price_history
        # Calculate the requested averages
        for i, g in enumerate(sorted(self.season_ticket_groups)):
            locs = self.season_ticket_groups[g]['locs']
            for p in averages_to_calculate:
                try:
                    getattr(self, p)[g] = caph(seat_locs = locs, **settings[p])
                    getattr(self, p + "_rel")[g] = copy.deepcopy(getattr(self, p)[g])
                    getattr(self, p + "_rel")[g]['price'] = getattr(self, p + "_rel")[g]['price'] - self.season_ticket_groups[g]['price']
                except EmptySeatGroupError:
                    # print("Caught EmptySeatGroupError for group {0}, average {1}- setting to NaN".format(g, settings[p]))
                    getattr(self, p)[g] = np.nan
                    getattr(self, p + "_rel")[g] = np.nan

    def average_price_history(self, price_type = 'sales', **kwargs):
        """
        Binding to use self.chronology.calc_average_price_history

        See SeatGroupChronology.calc_average_price_history() for more details.

        :param seat_locs:
        :param average_type:
        :param moving_average_timedelta:
        :param price_type:
        :param filter_func:
        :return:
        """
        # SGC's calc_average_price_history will not know about filtering at the Event level.  Instead interpret the
        # price_type here, then invoke calc_average_price_history on the correct SGC.  this invocation uses price_type
        # == listed because, once interpreted here, we want the average on the entire chosen SGC
        if price_type == 'sales_filtered':
            sgc = self.sales_filtered
        elif price_type == 'sales':
            sgc = self.sales
        elif price_type == 'listed':
            sgc = self.chronology
        else:
            raise SeatGroupError("Unknown price_type '{0}'".format(price_type))
        return sgc.calc_average_price_history(price_type = 'listed', **kwargs)

    def plot_price_history(self, groups='all', price_type='rel', prefix="",
                           plot_date_relative_to_event=True, xlim=None, ylim=None,
                           plot_listed=True,
                           plot_filtered_out_sales=True,
                           plot_sales_cumulative_average=True, plot_listings_cumulative_average=True,
                           plot_sales_moving_average = True, plot_listings_moving_average = True,
                           included_plot_variables = None):
        """
        Plot price versus time for the event by season ticket groups, (DISABLED: filtering prices by function f).

        TODO: This can be refactored a lot to make the code shorter
        TODO: Update this docstring

        :param price_type: rel for relative prices, abs for absolute
        :param f: (DISABLED) Same format as f in SGC.get_prices()
        :param plot_date_relative_to_event: False: Plot dates as stored in SGC
                                True: Plot dates relative to the event's data in self.meta (eg: Event-1 day, -2 days...)
                                A timepoint: Plot dates relative to the specified timepoint
        :param plot_listed: Add all available tickets at the end of the chronology to the figure
        :return: None
        """
        # if ylim is None:
        #     ylim = (-200, 200)
        if price_type == 'rel':
            sgc = self.sales_filtered_rel
        elif price_type == 'abs':
            sgc = self.sales_filtered
        else:
            raise ValueError("Invalid price_type '{0}' - must be 'abs' or 'rel'".format(price_type))

        # Validate plot_date_relative_to_event
        if plot_date_relative_to_event is True:
            plot_date_relative_to_event = self.datetime
        elif not isinstance(plot_date_relative_to_event, datetime.datetime):
            raise ValueError("normalize_dates must be True, False, or a datetime object")

        all_plot_variables = ['sales_min_average',
                              'listed_min_average',
                              'sales_filtered_average',
                              'listed_filtered_average',
                              'sales_average',
                              'listed_average',
                              'sales_min_moving_average',
                              'listed_min_moving_average',
                              'sales_filtered_moving_average',
                              'listed_filtered_moving_average',
                              'sales_moving_average',
                              'listed_moving_average',
                              'sales_filtered_min_moving_average',
                              ]
        if included_plot_variables:
            unknown_variables = [v for v in included_plot_variables if v not in all_plot_variables]
            if len(unknown_variables) > 0:
                raise ValueError("Unknown plot variables: {0}".format(unknown_variables))
        elif included_plot_variables is None:
            included_plot_variables = self.default_averages_to_calculate
        else:
            included_plot_variables = []
        # if price_type == 'rel':
        #     included_plot_variables = [x + "_rel" for x in included_plot_variables]

        main_color = 'k'
        plotstyle = {
            'sales_min_average': {'color': 'r', 'linestyle': '-', 'marker': None},
            'listed_min_average': {'color': 'r', 'linestyle': '-', 'marker': 'x'},
            'sales_filtered_average': {'color': 'b', 'linestyle': '--', 'marker': None},
            'listed_filtered_average': {'color': 'b', 'linestyle': '--', 'marker': 'x'},
            # 'sales_average': {'color': XXX, 'linestyle': ':', 'marker': None},
            # 'listed_average': {'color': XXX, 'linestyle': ':', 'marker': None},
            'sales_min_moving_average': {'color': 'r', 'linestyle': '-', 'marker': None},
            'listed_min_moving_average': {'color': 'r', 'linestyle': '-', 'marker': 'x'},
            'sales_filtered_min_moving_average': {'color': 'r', 'linestyle': '--', 'marker': None},
            'sales_filtered_moving_average': {'color': 'g', 'linestyle': '--', 'marker': None},
            'listed_filtered_moving_average': {'color': 'b', 'linestyle': '--', 'marker': 'x'},
            'sales_moving_average': {'color': 'y', 'linestyle': '--', 'marker': None},
            # 'listed_moving_average': {'color': XXX, 'linestyle': '-', 'marker': None},
       }

        if groups == 'all':
            groups = sorted(self.season_ticket_groups)


        plt.style.use('ggplot')
        for i, g in enumerate(groups):
            # NEED BETTER HANDLING OF GROUPS THAT ARE EMPTY
            print("Plotting group {0}".format(g))
            try:
                fig, ax = plt.subplots()

                # Plot all listed tickets
                if plot_listed:
                    locs = self.season_ticket_groups[g]['locs']
                    listed = self.chronology.get_seats(seat_locs = locs).get_prices(f = None)
                    if len(listed) > 0:
                        print("Found tickets listed - plotting")
                        if price_type == 'rel':
                            listed['price'] = listed['price'] - self.season_ticket_groups[g]['price']
                        dates = listed['timepoint']
                        #
                        # remaining_rel = (sg[last_tp].get_seats_as_seatgroup(seat_locs=locs, fail_if_missing=False) - self.season_tickets).get_prices()
                        # dates = [last_tp] * len(remaining_rel)
                        # if plot_date_relative_to_event is False:
                        #     dates = [last_tp] * len(remaining_rel)
                        if plot_date_relative_to_event is False:
                            # ax.plot_date(dates, remaining_rel, 'x', label=g + " Unsold", color=main_color)
                            ax.plot_date(dates, listed['price'], 'x', label=g + " Unsold ({0})".format(len(listed)), color='grey')
                        elif plot_date_relative_to_event:
                            dates = [(d - plot_date_relative_to_event).total_seconds() / 86400.0 for d in dates]
                            # ax.plot(dates, remaining_rel, 'x', label=g + " Unsold ({0})".format(len(remaining_rel)), color=main_color)
                            ax.plot(dates, listed['price'], 'x', label=g + " Unsold ({0})".format(len(listed)), color='grey')
                        else:
                            raise ValueError("normalize_dates must be True, False, or a datetime object")
                    else:
                        print("Listed tickets is empty - skipped for this group")

                # Plot any requested additional variables (different types of averages)
                for v in included_plot_variables:
                    if price_type == 'rel':
                        data_name = v + "_rel"
                    elif price_type == 'abs':
                        data_name = v
                    print('plotting data from {0}'.format(data_name))
                    avg = getattr(self, data_name)[g]
                    try:
                        len(avg)
                    except TypeError:
                        print("Unknown type for {0} - skipping".format(v))
                        continue
                    c = plotstyle[v]['color']
                    label = v
                    ls = plotstyle[v]['linestyle']
                    m = plotstyle[v]['marker']

                    if plot_date_relative_to_event is False:
                        ax.plot_date(avg['timepoint'], avg['price'], ls, label=label, color=c, marker=m)
                    else:
                        dates = [(d - plot_date_relative_to_event).total_seconds() / 86400.0 for d in avg['timepoint']]
                        ax.plot(dates, avg['price'], ls, label=label, color=c, marker=m)

                # Plot unfiltered sales first, if requested (so they sit behind the filtered sales)
                if plot_filtered_out_sales:
                    if price_type == 'rel':
                        sgc_uf = self.sales_rel
                    elif price_type == 'abs':
                        sgc_uf = self.sales
                    plot_uf = False
                    try:
                        sales_uf_all = sgc_uf.get_seats(self.season_ticket_groups[g]['locs']).get_prices(f=None)
                        plot_uf = True
                    except EmptySeatGroupError:
                        pass

                    if plot_uf:
                        print("Found unfiltered sales - plotting")

                        dates_all = sales_uf_all['timepoint']
                        if plot_date_relative_to_event is False:
                            ax.plot_date(dates_all, sales_uf_all['price'], ".", label=g + " Sales Filtered Out", color='r')
                        elif plot_date_relative_to_event:
                            # Is this better served as a SGC property, or at least method?  Will it get used elsewhere?
                            dates_all = [(d - plot_date_relative_to_event).total_seconds() / 86400.0 for d in dates_all]
                            ax.plot(dates_all, sales_uf_all['price'], ".", label=g + " Sales Filtered Out", color='r')
                        else:
                            raise ValueError("normalize_dates must be True, False, or a datetime object")
                    else:
                        print("Unfiltered sales is empty - skipped for this group")

                # Plot sales (all sales plotted, but minimum sales highlighted)
                # Move these down to where data actually gets plotted?  Dont think they're needed up here
                plot_sales = False
                try:
                    sales = sgc.get_seats(self.season_ticket_groups[g]['locs']).get_prices(f = np.min)
                    sales_all = sgc.get_seats(self.season_ticket_groups[g]['locs']).get_prices(f = None)
                    plot_sales = True
                except EmptySeatGroupError:
                    pass
                if plot_sales:
                    print("Found filtered sales - plotting")
                    dates = sales['timepoint']
                    dates_all = sales_all['timepoint']
                    if plot_date_relative_to_event is False:
                        ax.plot_date(dates, sales['price'], "-", marker='.', label=g, color=main_color)[0]
                        ax.plot_date(dates_all, sales_all['price'], ".", color=main_color)
                    elif plot_date_relative_to_event:
                        # Is this better served as a SGC property, or at least method?  Will it get used elsewhere?
                        dates = [(d - plot_date_relative_to_event).total_seconds() / 86400.0 for d in dates]
                        dates_all = [(d - plot_date_relative_to_event).total_seconds() / 86400.0 for d in dates_all]
                        ax.plot(dates, sales['price'], "-", label=g + "({0})".format(len(sales_all)), marker='.', color=main_color)[0]
                        ax.plot(dates_all, sales_all['price'], ".", color=main_color)
                        ax.set_xlim((None, 1))
                    else:
                        raise ValueError("normalize_dates must be True, False, or a datetime object")
                else:
                    print("Filtered sales is empty - skipped for this group")

                ax.set_title("vs {1} on {0} (group {2})".format(self.datetime, self.opponent, g))
                if xlim is None:
                    xlim = (self.chronology.sorted_timepoints[0] - datetime.timedelta(days=1), self.datetime + datetime.timedelta(days=1))
                    if plot_date_relative_to_event:
                        xlim = ((xlim[0] - plot_date_relative_to_event).total_seconds() / 86400.0,
                                (xlim[1] - plot_date_relative_to_event).total_seconds() / 86400.0)
                ax.set_xlim(xlim)
                ax.set_ylim(ylim)
                if price_type == 'rel':
                    ax.set_ylabel("Sale Price Relative to Season Ticket Price (${0})".format(
                        self.season_ticket_groups[g]['price']))
                elif price_type == 'abs':
                    ax.set_ylabel("Sale Price".format(self.season_ticket_groups[g]['price']))
                if plot_date_relative_to_event is False:
                    ax.set_xlabel("Date")
                else:
                    ax.set_xlabel("Days Before Event")
                plt.legend(loc='upper left', fontsize='x-small')
                fig.autofmt_xdate()
                fig.savefig(prefix + g + ".png")
                plt.close(fig)
            except Exception as e:
                print("LIKELY EXCEPTION DUE TO EMPTY GROUPS - NEED TO IMPROVE THIS")
                plt.close(fig)
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

    def summarize(self, price_type='rel', ticket_type='sales_filtered'):
        """
        Summarize high level data about an event and return as a dictionary.

        :param price_type: Relative (to season ticket price) or absolute ticket pricing
        :param ticket_type: Sales, sales_filtered, listed tickets
        :return: Dict with fields
            count: number of seats (including duplicate locations)
            mean: mean seat price
            std: standard deviation of seat price
            min: minimum seat price
            25%: 25th percentile seat price
            50%: 50th percentile seat price
            75%: 75th percentile seat price
            max: Maximum seat price
            by_group: {
                        season_ticket_group_1: {
                                                Same fields as upper level, but for each group
                                               }
                        season_ticket_group_2: { }
                        ...
                      }
            (NOT YET IMPLEMENTED) by_timepoint: {
                                                    nested by group?  overall?
                        }
        """

        # Build name of property to use here (is this a good way of doing this?  Makes the code
        # a bit more straight forward, but feels funny...
        if ticket_type not in ['sales', 'sales_filtered', 'listed']:
            raise ValueError("Invalid ticket_type '{0}'".format(ticket_type))
        name = ticket_type
        if price_type == 'rel':
            name = ticket_type + "_" + price_type
        elif price_type == 'abs':
            pass
        else:
            raise ValueError("Invalid price_type '{0}'".format(price_type))
        sgc = getattr(self, name)

        ret = sgc.describe()

        # Embed settings
        ret['price_type'] = price_type
        ret['ticket_type'] = ticket_type

        ret['by_group'] = {}

        for g in self.season_ticket_groups:
            locs = self.season_ticket_groups[g]['locs']
            group_sgc = sgc.get_seats(seat_locs = locs)
            ret['by_group'][g] = group_sgc.describe()

        return ret

    @classmethod
    def get_season_ticket_groups(cls):
        """
        Return a season_ticket_groups dictionary without a specific eventid.

        :return: Dict
        """
        event = cls(add_meta=False)
        return event.season_ticket_groups

    @classmethod
    def profit_margin(cls, df):
        """
        Returns a DataFrame of event profit margin given a DataFrame df of event profit.

        :param df: A multiindex DataFrame with indices of EventID and columns of (Season Ticket Group, [statistics])
        :return: A new DataFrame of similar form to df, but with all group statistics normalized by their respective Season
                 Ticket Prices.  The Season Ticket group "All" and all Standard Deviations are dropped from the returned DataFrame
        """
        pm = df.drop("std", axis=1, level=1).drop('All', axis=1, level=0)

        # Columns to normalize by season ticket price
        lvl1 = ["mean", "min", "25%", "50%", "75%", "max"]

        # Loop through season ticket prices, normalizing all data in that group
        season_ticket = cls.season_ticket_to_df()
        for index, row in season_ticket.iterrows():
            cols = list(product((index,), lvl1))
            pm[cols] = pm[cols] / row['Season Ticket Price']

        return pm

    @classmethod
    def profit_by_group(cls, df, sort_by='25%', profit_type='per_game'):
        """
        Returns a DataFrame of profit grouped by Season Ticket Group, with rows as groups and columns as statistics.

        Convenience binding to invoke the profit_by_group() function.
        :param sort_by: Sort returned df by this
        :param profit_type: per_game: Profit per game per ticket
                            per_season: Profit per season per ticket
        :return: DataFrame with rows of Season Ticket Group and columns of statistics from the original df
                           (eg: 25th percentile, mean, ...)
        """
        return profit_by_group(df, event_class=cls, sort_by=sort_by, profit_type=profit_type)

    @classmethod
    def profit_margin_by_group(cls, df, sort_by='25%'):
        """
        Convenience function to chain profit_margin and profit_by_group together
        """
        pm = cls.profit_margin(df)
        return cls.profit_by_group(pm, profit_type='per_game', sort_by=sort_by)

    @classmethod
    def profit_by_day(cls, df):
        """
        Convenience binding to profit_by_day
        """
        return profit_by_col(df, col=("Meta", "Day"), sort_by='index')

    @classmethod
    def plot_profit_by_day(cls, df, sort_by='index', statistic="25%", kind='box', ax=None, **kwargs):
        return plot_profit_by_col(df, col=("Meta", "Day"), sort_by=sort_by, statistic=statistic, kind=kind, ax=ax, **kwargs)

    @classmethod
    def profit_by_col(cls, df, col, sort_by='index'):
        """
        Convenience binding to profit_by_day
        """
        return profit_by_col(df, col, sort_by=sort_by)

    @classmethod
    def plot_profit_by_col(cls, df, col, sort_by='index', statistic='25%', kind='box', ax=None, **kwargs):
        return plot_profit_by_col(df, col, sort_by=sort_by, statistic=statistic, kind=kind, ax=ax, **kwargs)

    @classmethod
    def season_ticket_to_df(cls):
        stg = cls.get_season_ticket_groups()

        # np.array of group, group_ticket_price
        data = np.array([(g, float(stg[g]['price'])) for g in stg.keys()])

        # Dataframe with index of group, column of price
        df = pd.DataFrame(data[:, 1], index=data[:, 0], columns=['Season Ticket Price'], dtype=np.float)
        return df

class Panthers(Event):
    def __init__(self, price_override=None, add_meta=True, **kwargs):
        super().__init__(**kwargs)
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
        self.init_season_ticket_seatgroup(price_override=price_override)

        # Custom inclusion list (only sections in this list are loaded)
        self.include = set()
        for s in self.season_ticket_groups:
            self.include.update(self.season_ticket_groups[s]['locs'])

        if add_meta:
            self.event_info_file = "2017_Panthers_event_data.json"
            self.add_meta()

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

class Hornets(Event):
    def __init__(self, price_override=None, add_meta=True, **kwargs):
        super().__init__(**kwargs)
        self.namemap = [
            (r'(?i)Inner Circle Club Sideline\s+', ''),
            (r'(?i)Inner Circle Club Sideline\s+', ''),
            (r'(?i)Club Baseline L\s+', 'L'),
            (r'(?i)Club Sideline\s+', ''),
            (r'(?i)Lower Level Baseline\s+', ''),
            (r'(?i)Lower Level Corners\s+', ''),
            (r'(?i)Upper Level Baseline\s+', ''),
            (r'(?i)Upper Level Center Court\s+', ''),
            (r'(?i)Upper Level Center Row \w\s+', ''),
            (r'(?i)Upper Level Corners\s+', ''),
            (r'(?i)Club\s+', ''),
            (r'(?i)Courtside\s+', ''),
        ]

        # Custom ignore list (these sections have no associated season ticket price, so no need of them)
        self.ignore = []

        # Build season tickets
        self.init_season_ticket_groups()
        self.init_season_ticket_seatgroup(price_override=price_override)

        # Custom inclusion list (only sections in this list are loaded)
        self.include = set()
        for s in self.season_ticket_groups:
            self.include.update(self.season_ticket_groups[s]['locs'])

        if add_meta:
            self.event_info_file = "2017_Hornets_event_data.json"
            self.add_meta()

    def init_season_ticket_groups(self):
        """
        Initializes season ticket groupings for a Panthers event.

        :return: None
        """

        rows_lower_front = ["A1", "A2", "A3"]
        rows_lower_mid_mid = list("ABCDEFGHIJ")
        rows_lower_low = list("ABCDEFGH")
        rows_lower_mid = list("IJKLM")
        rows_lower_mid_high = list("KLMNOPQ")
        rows_lower_mid_higher = ["R"]
        rows_upper_front = ["A1", "A2", "A3", "A4"] + list("ABCDEFGHI")
        rows_upper_mid = list("JKLMNOPQ")
        rows_upper_up = list("RSTUVWXYZ")

        secs_club_outside = [104, 106, 113, 115]
        secs_lower_baseline = [101, 102, 103, 107, 109, 110, 112, 116, 117]
        secs_upper_sideline = [207, 208, 209, 210, 224, 225, 226, 227]
        secs_upper_curve = [203, 204, 205, 206, 211, 212, 213, 214, 220, 221, 222, 223, 228, 229, 230, 231]
        secs_upper_baseline = [201, 202, 215, 216, 217, 218, 219, 232, 233]

        # sections = [104, 105, 106, 113, 114, 115]
        # rows = ['CS1', 'CS2']
        # self.season_ticket_groups['Courtside'] = {
        #     'locs': list(product(sections, rows)),
        #     'price': 0.0,
        # }

        sections = [105, 114]
        rows = rows_lower_front
        self.season_ticket_groups['ICC Center'] = {
            'locs': list(product(sections, rows)),
            'price': 315.0,
        }

        seats = list(product(secs_club_outside, rows_lower_front)) + list(product([103, 116], ["A1"]))
        self.season_ticket_groups['ICC Outside'] = {
            'locs': seats,
            'price': 285.00,
        }

        sections = [105, 114]
        rows = rows_lower_mid_mid
        self.season_ticket_groups['Low Club Center'] = {
            'locs': list(product(sections, rows)),
            'price': 160.0,
        }

        sections = secs_club_outside
        rows = rows_lower_low
        self.season_ticket_groups['Low Club Outside'] = {
            'locs': list(product(sections, rows)),
            'price': 140.0,
        }

        sections = [105, 114]
        rows = rows_lower_mid_high
        self.season_ticket_groups['Mid Clubs Center'] = {
            'locs': list(product(sections, rows)),
            'price': 134.0,
        }

        sections = secs_club_outside
        rows = rows_lower_mid
        self.season_ticket_groups['Mid Club Outside'] = {
            'locs': list(product(sections, rows)),
            'price': 134.0,
        }

        seats = list(product([105, 114], ["R"])) + list(product(secs_club_outside, [c for c in "NOPQRS"]))
        self.season_ticket_groups['High Club'] = {
            'locs': seats,
            'price': 105.00,
        }

        seats = list(product([101, 107, 109, 110, 117], ["A1", "A2", "A3"])) + list(product([103, 112, 116], ["A2", "A3"]))
        self.season_ticket_groups['Lower Baseline Front'] = {
            'locs': seats,
            'price': 108.00,
        }

        seats = list(product([102, 103, 107, 112, 116], rows_lower_mid_mid)) + list(
            product([101, 109, 110, 117], list("ABCDE")))
        self.season_ticket_groups['Lower Curve Baseline Low'] = {
            'locs': seats,
            'price': 85.00,
        }

        sections = ["L01", "L02", "L03"]
        self.season_ticket_groups['Ledge Baseline'] = {
            'locs': list(product(sections)),
            'price': 72.0,
        }

        sections = [102, 103, 107, 112, 116]
        rows = list("KLMNOPQR")
        seats = list(product(sections, rows)) + list(product([108, 111]))
        self.season_ticket_groups['Lower Curve Mid'] = {
            'locs': seats,
            'price': 65.0,
        }

        sections = [101, 109, 110, 117]
        rows = list("FGHIJKLMNOPQR")
        self.season_ticket_groups['Lower Baseline Mid'] = {
            'locs': list(product(sections, rows)),
            'price': 58.0,
        }

        sections = [101, 102, 103, 116, 117]
        rows = list("STUVWXYZ") + ["AA", "BB", "CC", "DD", "EE"]
        self.season_ticket_groups['Lower Curve Baseline High'] = {
            'locs': list(product(sections, rows)),
            'price': 48.0,
        }

        sections = secs_upper_sideline
        rows = list("AB")
        self.season_ticket_groups['Upper Sideline Front'] = {
            'locs': list(product(sections, rows)),
            'price': 42.0,
        }

        sections = secs_upper_sideline
        rows = list("CDEFGHI")
        self.season_ticket_groups['Upper Sideline Low'] = {
            'locs': list(product(sections, rows)),
            'price': 29.0,
        }

        sections = secs_upper_curve
        rows = rows_upper_front
        self.season_ticket_groups['Upper Curve Low'] = {
            'locs': list(product(sections, rows)),
            'price': 27.0,
        }

        sections = secs_upper_baseline
        rows = rows_upper_front
        self.season_ticket_groups['Upper Baseline Low'] = {
            'locs': list(product(sections, rows)),
            'price': 22.0,
        }

        sections = secs_upper_sideline
        rows = rows_upper_mid
        self.season_ticket_groups['Upper Sideline Mid'] = {
            'locs': list(product(sections, rows)),
            'price': 18.0,
        }

        sections = secs_upper_curve
        rows = rows_upper_mid
        self.season_ticket_groups['Upper Curve Mid'] = {
            'locs': list(product(sections, rows)),
            'price': 13.0,
        }

        sections = secs_upper_baseline
        rows = rows_upper_mid
        self.season_ticket_groups['Upper Baseline High'] = {
            'locs': list(product(sections, rows)),
            'price': 13.0,
        }

        sections = secs_upper_sideline
        rows = rows_upper_up
        self.season_ticket_groups['Upper Sideline High'] = {
            'locs': list(product(sections, rows)),
            'price': 14.0,
        }

        sections = secs_upper_curve
        rows = rows_upper_up
        self.season_ticket_groups['Upper Curve High'] = {
            'locs': list(product(sections, rows)),
            'price': 12.0,
        }

# Exceptions
class EventError(Exception):
    pass

def summarize_events(event_object, directory='./', save_to=None, eventids=None, tp_slice=None, ticket_type='sales_filtered'):
    """
    Scrape a directory for events, summarize them, and return summary as a Pandas DataFrame

    :param event_object: The event object to be used for creating events
    :param directory: Location to search for event JSON files
    :save_to: Filename to save the output DataFrame to as csv
    :param eventids: List of eventids to include in summary, or None to grab all events in the directory.
    :param tp_slice: tp_slice as defined in Event.scrape_timepoints_from_dir()
    :param event_kwargs: (UNUSED) Optional arguments to pass to the event constructor (in addition to eventid, which is always
                         passed)
    :param ticket_type: Type of tickets (sales, sales_filtered, listed) passed to event.summarize()
    :return: Pandas DataFrame
    """
    # Build DataFrame column multiindex
    days_of_week = {
        1: 'Monday',
        2: 'Tuesday',
        3: 'Wednesday',
        4: 'Thursday',
        5: 'Friday',
        6: 'Saturday',
        7: 'Sunday',
    }
    mkeys = ['vs', 'Day', 'Date']
    m_prod = product(("Meta", ), mkeys)
    groups = sorted(event_object.get_season_ticket_groups())
    groups_all = ['All'] + groups
    dkeys = ['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max', ]
    g_prod = product(groups_all, dkeys)
    all_keys = list(m_prod) + list(g_prod)
    index = pd.MultiIndex.from_tuples(all_keys) # Index for the columns

    # Find all relevant listings
    listings = find_listings_files(directory)
    n = len(listings)
    print("Found {0} listings".format(n))
    if eventids is not None:
        listings = {k: v for k, v in listings.items() if k in eventids} # Why build this as a dict? I never use the values
        print("{0} of {1} listings specified in eventids argument".format(len(listings), n))
    ids = sorted(listings)

    # Load data from relevant listings
    data = []
    for i, eventid in enumerate(ids):
        row = []
        print("Processing event {0}: {1}".format(i + 1, eventid))
        event = event_object(eventid=eventid)
        # Extract metadata
        row.append(event.opponent)
        row.append(days_of_week[event.datetime.isoweekday()])
        row.append(event.datetime)

        # Extract ticket data
        event.scrape_timepoints_from_dir(directory=directory, tp_slice=tp_slice)
        event.infer_chronological_changes()
        event.calc_all_average_price_history()
        # sales_filt_summary[eventid] = event.summarize(ticket_type=ticket_type)
        sales_filt_summary = event.summarize(ticket_type=ticket_type)
        row.extend(summary_to_list(sales_filt_summary, groups_all, dkeys))

        data.append(row)

    df = pd.DataFrame(data, columns=index, index=ids)
    df.index.rename("EventID", inplace=True)

    if save_to:
        df.to_csv(save_to)
    return df



# Functions for interpreting Event DataFrames from summarize_events
# Maybe you'd sometime want these outside the context of a
# Make these into a class?  Could also be class functions.  That makes sense as some need the event class (but a few dont)
# def profit_margin(df, event_class=None):

def profit_by_col(df, col, sort_by='index'):
    # Does sort_by even work if not 'index'?  These are multiindex columns...
    gb = df.groupby(by=[col])
    df_new = gb.mean()
    if sort_by == 'index':
        df_new.sort_index()
    elif sort_by:
        df_new.sort_values(sort_by, ascending=False, axis=0)
    return df_new

def plot_profit_by_col(df, col, sort_by='index', statistic="25%", kind='box', ax=None, **kwargs):
    """
    Convienance function to plot profit

    :param df: A profit or profit margin DataFrame in the Event.summarize_events() format.
    :param sub_col: OPTIONAL Subcolumn, such as "mean", to plot data by .  Although not necessary, recommended
                    at least if using a box plot
    :param ax: Axes object to plot on
    :param kwargs: other arguments passed to the plotter (formatting, etc)
    :return: axes object
    """
    if ax==None:
        fig, ax = plt.subplots()

    df = profit_by_col(df, col, sort_by=sort_by)
    if statistic:
        df = df.xs(statistic, level=1, axis=1)
    ax = df.T.plot(kind=kind, ax=ax, **kwargs)
    return ax

def profit_by_group(df, event_class=None, sort_by='25%', profit_type='per_game'):
    """
    Returns a DataFrame of profit grouped by Season Ticket Group, as defined in event_class, with rows as groups and columns as statistics.

    Convenience binding to invoke the profit_by_group() function.
    :param sort_by: Sort returned df by this
    :param profit_type: per_game: Profit per game per ticket
                        per_season: Profit per season per ticket
    :return: DataFrame with rows of Season Ticket Group and columns of statistics from the original df
                       (eg: 25th percentile, mean, ...)
    """
    series = []
    for g in df.columns.levels[0]:
        if g == 'Meta':
            continue
        avg = df[g].mean()
        avg.name = g
        series.append(avg)
    new_df = pd.DataFrame(series)

    # Reorder so count and std are first two columns
    front_cols = [c for c in ['count', 'std'] if c in new_df]
    #     other_cols = [c for c in list(new_df.columns) if c not in front_cols]
    other_cols = [c for c in ["mean", "min", "25%", "50%", "75%", "max"] if c in new_df]
    new_df = new_df[front_cols + other_cols]

    # Add season ticket prices, if requested
    if event_class is not None:
        season_ticket = event_class.season_ticket_to_df()
        new_df = pd.concat([new_df[['count']], season_ticket, new_df.drop(['count'], axis=1)], axis=1)

    if profit_type == 'per_season':
        new_df = new_df * 41
    elif profit_type == 'per_game':
        pass
    else:
        raise ValueError("Invalid profit_type '{0}'".format(profit_type))

    if sort_by is not None:
        new_df = new_df.sort_values(sort_by, ascending=False, axis=0)
    return new_df

def profit_by_day(df):
    """
    Return a DataFrame that has rows of Day of the Week and Columns of mean prices for different groups

    Sample recipe:
        only 25% profit by day for each group:
            df_new = profit_by_day(df).xs("25%", level=1, axis=1)
        plot only 25% profit by day for each group, as a boxplot:
            df_new = profit_by_day(df).xs("25%", level=1, axis=1)
            df_new.T.plot(kind='box')
            plt.show()

    :param df: A DataFrame in the form of Event.summarize_events return, or the profit margin equivalent.
    :return: A DaraFrame with rows of Day of the Week and Columns of mean prices for different groups

    """
    # Replaced with generic...
    return profit_by_col(df, col=('Meta', 'Day'), sort_by='index')

def plot_profit_by_day(df, sub_col="25%", kind='box', ax=None, **kwargs):
    """
    Convienance function to plot profit

    :param df: A profit or profit margin DataFrame in the Event.summarize_events() format.
    :param sub_col: OPTIONAL Subcolumn, such as "mean", to plot data by .  Although not necessary, recommended
                    at least if using a box plot
    :param ax: Axes object to plot on
    :param kwargs: other arguments passed to the plotter (formatting, etc)
    :return: axes object
    """
    if ax==None:
        fig, ax = plt.subplots()

    df = profit_by_day(df)
    if sub_col:
        df = df.xs(sub_col, level=1, axis=1)
    ax = df.T.plot(kind=kind, ax=ax, **kwargs)
    return ax

# def profit_by_day(df):
# DEPRECIATED
#     # Recipe:
#     #  25% profit by day for each group
#     #  df_new = profit_by_day(df).xs("25%", level=1, axis=1)
#     col = ('Meta', 'Day')
#     gb = df.groupby(by=[col])
#     p_by_day = gb.mean()
#     p_by_day.sort_index()
#     return p_by_day



# Helper
def mygen(start=0, stop=100, inc=1):
    """A simple custom generator"""
    i = start
    while i < stop:
        yield i
        i += inc

def find_listings_files(directory):
    listings = {}
    for fn in os.listdir(directory):
        full_fn = os.path.join(directory, fn)
        if os.path.isfile(full_fn):
            try:
                this_id, this_time = parse_listings_fn(fn)
            except:
                # print(
                #     "DEBUG: WARNING: {0} cannot be parsed into listings filename format - skipping".format(fn))
                continue
            try:
                listings[this_id][this_time] = full_fn
            except KeyError:
                listings[this_id] = {this_time: full_fn}
    return listings

def parse_listings_fn(fn):
    match = re.match(r'(\d+)_(.+)\.json', fn)
    eventid = int(match.group(1))
    timepoint = datetime.datetime.strptime(match.group(2), DATETIME_FORMAT)
    return (eventid, timepoint)

def summary_to_list(summary, groups, keys):
    """
    Convert an event summary dict to a single list of numbers

    Return is essentially the data corresponding to the tuple keys you get by running product(groups, keys)

    :param summary: Event summary dict
    :param groups: List of ticket groups to be included in the returned list (entry of "All" means to include the upper
                   level summary statistics for this event.
    :param keys: Data labels to include for each group
    :return: List
    """
    row = []
    for g in groups:
        # Special case for high level data
        if g == 'All':
            row.extend([summary.get(k, np.nan) for k in keys])
        else:
            try:
                row.extend([summary['by_group'][g].get(k, np.nan) for k in keys])
            except KeyError:
                row.extend([np.nan] * len(keys))
    return row