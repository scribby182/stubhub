import datetime
import re
import os
from pprint import pprint
import json
from Seats import DuplicateSeatError, SeatGroupError, SeatGroupChronology, SeatGroup, Seat
from stubhub_list_scrape import DATETIME_FORMAT

class Event(object):
    """
    Object for a event such as a game or concert.
    """
    def __init__(self):
        self.chronology = SeatGroupChronology()
        self.datetime = None
        self.location = None
        self.meta = {} # For things like home/away team, etc.
        self.sales = None
        self.added = None
        self.new_price = None
        self.new_listid = None

    def add_meta(self, json_file):
        """
        Add an Event's metadata from a JSON formatted event file.
        :param json_file:
        :return:
        """
        # Should there be a non-JSON way to do this too?  Maybe this is dict based and then the JSON one loads and
        # formats to a standard dict?
        raise NotImplementedError()

    def add_timepoint(self, timepoint, json_file):
        """
        Add a SeatGroup timepoint to the event's chronology from a JSON formatted event file, identified by a timepoint

        Possible improvement: Could update sales/add/... Chronologies for each seatgroup added.
        Could run prev_diff = diff(this_timepoint, prev), next_diff = diff(next_timepoint, this_timepoint), then
        sales.add(prev_diff, this_timepoint), sales.remove(next_diff), and sales.add(next_diff, next_timepoint).
        Probably want this auto_update togglable, and group-adds could disable to avoid remaking sales infor that gets
        rewritten immediately afterwards.


        :param timepoint: A datetime object (used as the key to identify the timepoint)
        :param json_file: Filename of a JSON file with event listings data
        :return: None
        """
        self.chronology.add_seatgroup_from_event_json(timepoint, json_file)


    def scrape_timepoints_from_dir(self, eventid, directory):
        """
        Scrapes directory for JSON listings files of format "eventid_YYYY-MM-DD_hh-mm-ss.json" and adds them to event.

        :param eventid: EventID to look for in directory (only adds events with this ID)
        :param directory: Directory to search for listing files
        :return: None
        """

        def parse_listings_fn(fn):
            match = re.match(r'(\d+)_(.+)\.json', fn)
            eventid = int(match.group(1))
            timepoint = datetime.datetime.strptime(match.group(2), DATETIME_FORMAT)
            return (eventid, timepoint)

        # Get all filenames in the directory, parse them into (eventid, datetime), then add and that match the requested
        # eventID to the Event
        for fn in os.listdir(directory):
            full_fn = os.path.join(directory, fn)
            if os.path.isfile(full_fn):
                try:
                    this_id, this_time = parse_listings_fn(fn)
                except:
                    print(
                        "DEBUG: WARNING: {0} cannot be parsed into listings filename format - skipping".format(
                            fn))
                    continue
                if this_id == eventid:
                    self.add_timepoint(this_time, full_fn)
                else:
                    print("DEBUG: {0} is not part of event {1} - skipping".format(fn, eventid))
            else:
                print("DEBUG: {0} is not a file".format(fn))

    def infer_chronological_changes(self):
        diff = self.chronology.find_differences()
        self.sales = diff['removed']
        self.added = diff['added']
        self.new_price = diff['new_price']
        self.new_listid = diff['new_listid']
    # Properties
    # Add day_of_week property?
    # Add time of event/date of event, which pulls from the self.datetime?

class Panthers(Event):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.namemap = [
            (r'(?i)\s*Club\s*', ''),
            (r'(?i)\s*I+\s*', ''),
            (r'(?i)\s*Terrace\s*', ''),
            (r'(?i)\s*lower\s*', ''),
            (r'(?i)\s*middle\s*', ''),
            (r'(?i)\s*upper\s*', ''),
            (r'(?i)\s*end zone\s*', ''),
            (r'(?i)\s*premium\s*', ''),
            (r'(?i)\s*sideline\s*', ''),
        ]

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