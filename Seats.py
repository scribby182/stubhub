import numpy as np
import datetime
from pprint import pprint
import bisect
import json

class Seat(object):
    """
    Object to hold data associated with a single seat
    """
    def __init__(self, price=None, available=None, facevalue=None, list_id=None):
        self.price = price
        self.facevalue = facevalue
        self.available = available
        self.list_id = list_id
        # These are what are used in evaluating equality.  Put them up here so I don't forget to add to the list
        # if we add new attributes
        self._equality_attributes = ['price', 'facevalue', 'available', 'list_id']

    def __eq__(self, other):
        """
        Evaluate equality of two Seats by comparing all their important attributes

        :param other: Another Seat
        :return: Boolean
        """
        for attr in self._equality_attributes:
            try:
                if getattr(self, attr) == getattr(other, attr):
                    continue
                else:
                    return False
            except AttributeError:
                return False
        return True

    def __repr__(self):
        return "{0}(price={1}, available={2})".format(type(self).__name__, self.price, self.available)


class SeatGroup(object):
    """
    Object to hold and interact with either a group of Seats or or SeatGroups
    """
    def __init__(self):
        self.seats = {}
        self.sorted_names = []

    def __len__(self):
        """
        Return the number of seats in the SeatGroup, including seats in nested groups.

        :return:
        """
        length = 0
        for seatname in self.seats:
            try:
                length += len(self.seats[seatname])
            except TypeError:
                length += 1
        return length

    def __eq__(self, other):
        """
        Compare two SeatGroups by ensuring they have identical seat entries.

        :param other: Another SeatGroup
        :return: Boolean
        """
        for seatname in (self.seats.keys() | other.seats.keys()):
            try:
                if self.seats[seatname] == other.seats[seatname]:
                    continue
                else:
                    return False
            except KeyError:
                return False
        # If I get here, we're all the same!
        return True

    def add(self, seat, name, make_deep_groups=True):
        """
        Add a Seat ot SeatGroup to the object

        :param seat:
        :param name:
        :param make_deep_groups: If True, if a seat is added to a SeatGroup that does not exist, that group will be
                                 created.  ie:
                                    sg = SeatGroup()
                                    sg.add(some_seat, (rowA, seat1), make_deep_groups=True)
                                 Will create a seatgroup sg that has a nested seatgroup sg.seats['rowA'], where the
                                 nested group contains 'some_seat'
                                 If False, will raise an exception if all subgroups do not already exist.
        :return: None
        """
        if isinstance(name, tuple) or isinstance(name, list):
            # Seat being added has multi-level name.  Could be len=1 (this level), len>1 (deeper level).
            if len(name) == 1:
                # This is the level where the seat should be added.  Just modify name binding and continue below
                name = name[0]
                # Note: This does not return, it continues below this if/else.  Flow is a little confusing, refactor?
            else:
                # Seat is added deeper than this group.  Check if it exists (and optionally create it), then recurse
                this_name = str(name[0])
                if not this_name in self.seats:
                    if make_deep_groups:
                        sg = SeatGroup()
                        self.add(seat=sg, name=this_name)
                    else:
                        raise SeatGroupError("Cannot add seat '{0}', SeatGroup '{1}' not defined".format(name, name[0]))
                self.seats[this_name].add(seat, name[1:], make_deep_groups=make_deep_groups)
                return

        # Internally, names are always treated as strings
        name = str(name)

        if isinstance(seat, Seat) or isinstance(seat, SeatGroup):
            if name in self.seats:
                raise DuplicateSeatError("Seat \"{0}\" already in use".format(name))
            else:
                # Store the Seat and maintain a sorted list of names
                bisect.insort(self.sorted_names, name)
                self.seats[name] = seat
        else:
            raise SeatGroupError("Seat '{0}' must be a Seat or SeatGroup object - found {1}".format(name, type(seat)))

    def remove(self, name, remove_deep_seats=True, cleanup_empty_groups=True):
        """
        Remove a Seat of SeatGroup from the object

        :param name: Name of the seat to be removed.  Can be a tuple describing a nested seat of remove_deep_seats
                     is True.
        :param remove_deep_seats: Boolean.  If True, name can be a tuple referring to seats nested in deep SeatGroups
        :param cleanup_empty_groups: Boolean.  If True, any recursive seat removal that leaves an empty SeatGroup will
                                     also remove the empty parent SeatGroup.
        :return: None
        """
        if isinstance(name, tuple) or isinstance(name, list):
            # Seat being removed has multi-level name.  Could be len=1 (this level), len>1 (deeper level).
            if len(name) == 1:
                # This is the level where the seat should be added.  Just modify name binding and continue below
                name = name[0]
                # Note: This does not return, it continues below this if/else.  Flow is a little confusing, refactor?
            else:
                # Seat being removed is deeper than this group.  Recurse if allowed.
                if remove_deep_seats:
                    this_name = str(name[0])
                    if this_name not in self.seats or this_name not in self.sorted_names:
                        raise SeatGroupError("Seat \"{0}\" is not in this group - cannot remove".format(name))
                    self.seats[this_name].remove(name[1:], remove_deep_seats=remove_deep_seats)
                    if len(self.seats[this_name]) == 0 and cleanup_empty_groups:
                        # Remove the empty parent SeatGroup
                        self.seats.pop(this_name)
                        self.sorted_names.remove(this_name)
                else:
                    raise SeatGroupError("Cannot remove seat '{0}', remove_deep_seats is False".format(name))
                return None

        # Internally, names are always treated as strings
        name = str(name)
        try:
            # Remove seat and its name
            self.seats.pop(name)
            self.sorted_names.remove(name)
        except (KeyError, ValueError):
            raise SeatGroupError("Seat \"{0}\" is not in this group - cannot remove".format(name))

    def display(self):
        """
        A user-friendly printing of the SeatGroup's content.
        This really is what __str__ should be, but I don't want this printing all the time (it will be huge!)
        :return:
        """
        locs = self.get_locs()
        seats = self.get_seats_as_list(locs)
        for s in zip(locs, seats):
            print(s)

    def get_seats_as_seatgroup(self, seat_locs):
        """
        Return a SeatGroup of seats described by an iterable of seat location tuples.

        Structure of the original group is preserved (so if seats were broken into SeatGroups in the original SeatGroup,
        they are returned in a similar way in the new SeatGroup

        :param seat_locs:
        :return:
        """
        seats_as_list = self.get_seats_as_list(seat_locs)
        seats = zip(seat_locs, seats_as_list)
        newsg = SeatGroup()
        for loc, seat in seats:
            newsg.add(seat, loc)
        return newsg

    def get_seats_as_list(self, seat_locs):
        """
        Return a list of seats described by an iterable of seat location tuples

        :param seat_locs:
        :return: List of seat objects
        """
        # TODO: Add wildcards, ie: loc=(section1, rowA, *)?  Or can this be covered by just get(loc=(section1, rowA)) then an action on that new group?
        returned = [None] * len(seat_locs)
        for i, loc in enumerate(seat_locs):
            if not (isinstance(loc, tuple) or isinstance(loc, list)):
                raise SeatGroupError("Invalid seat_loc - must be a list of tuples")
            elif len(loc) == 1:
                returned[i] = self.seats[loc[0]]
            else:
                try:
                    # Get will return a list of seats of length 1, but we just want the seat
                    returned[i] = self.seats[loc[0]].get_seats_as_list([loc[1:]])[0]
                except AttributeError:
                    raise SeatGroupError("Seat '{0}' is a Seat but was used as a SeatGroup with location '{1}'".format(loc[0], loc))
        return returned

    def get_locs(self, seat_locs=None, depth=None):
        """
        Returns a list of tuples identifying all the seats in this SeatGroup, including seats nested in other SeatGroups
        :return:
        """
        if seat_locs is None:
            if depth == 1:
                return self.sorted_names
            else:
                if depth is not None:
                    depth = depth - 1
                seat_list = []
                for seat in self.sorted_names:
                    try:
                        seats = self.seats[seat].get_locs(depth=depth)
                        seat_list.extend([(seat, *s) for s in seats])
                    except AttributeError:
                        # This is a base level seat and does not need to be handled recursively
                        seat_list.append((seat,))
                return seat_list
        else:
            seat_list = []
            for seat_loc in seat_locs:
                # Get the seat referenced in seat_loc.  Use get_seats_as_list[0] instead of get_seats_as_seatgroup
                # because the latter will preserve the entire structure (ie, get([(lvl1, lvl2, lvl3)]) returns a 3 lvl
                # SeatGroup instead of just the SeatGroup at lvl3
                # Get the list of seats in the location in question, then append the rest of the location back on the
                # front of the tuple for full context
                # seat_list.extend(self.get_seats_as_list([seat_loc])[0].get_locs(depth=depth))
                these_seats = [(*seat_loc, *loc) for loc in self.get_seats_as_list([seat_loc])[0].get_locs(depth=depth)]
                seat_list.extend(these_seats)
            return seat_list

    def difference(self, other_sg):
        """
        Find the differences between this and other_sg and return them.

        :param other_sg:
        :return: Dict of added, removed, new_price, new_listid
        """
        # Get all seats from both SeatGroups
        this_locs = self.get_locs()
        other_locs = other_sg.get_locs()
        all_locs = set(this_locs + other_locs)

        res = {
            'added': SeatGroup(),
            'removed': SeatGroup(),
            'new_price': SeatGroup(),
            'new_listid': SeatGroup(),
        }

        # For each seat, find any differences
        for loc in all_locs:
            try:
                this_seat = self.get_seats_as_list([loc])[0]
            except KeyError:
                this_seat = None
            try:
                other_seat = other_sg.get_seats_as_list([loc])[0]
            except KeyError:
                other_seat = None
            if this_seat == other_seat:
                continue
            elif this_seat is None:
                # Removed seat
                res['removed'].add(other_seat, loc)
            elif other_seat is None:
                # Added seat
                res['added'].add(this_seat, loc)
            else:
                # Could be more than one of these at a time
                if this_seat.price != other_seat.price:
                    # Price change
                    res['new_price'].add(this_seat, loc)
                if this_seat.list_id != other_seat.list_id:
                    # Listid change (new listing)
                    res['new_listid'].add(this_seat, loc)

        return res

    @property
    def price(self):
        """
        Return the average price of all seats in the group and return the value.
        Implemented as a property to mimic Seat.price

        NOTE: Is a recursive implementation faster, or would using get_locs, get_seat_list, then sum prices be faster?

        :return: Float of average ticket price in the group
        """
        n = 0.0
        price_sum = 0.0
        for seatname in self.seats:
            this_price = float(self.seats[seatname].price)
            try:
                this_n = len(self.seats[seatname])
            except TypeError:
                this_n = 1
            n += this_n
            price_sum += this_price * this_n
        return price_sum / n

    @classmethod
    def init_from_event_json(cls, json_file):
        """
        Populate and return a SeatGroup object fro4m a JSON formatted event file

        :param json_file: Filename of a JSON file with event listings data
        :return: None
        """
        # Load event information to dictionary
        with open(json_file, 'r') as f:
            event_dict = json.load(f)

        sg = cls()
        for listing in event_dict['listing']:
            # Unpack and handle possible missing values
            try:
                facevalue = listing['faceValue']['amount']
            except KeyError:
                facevalue = None
            price = listing['currentPrice']['amount']
            list_id = listing['listingId']
            section = listing['sellerSectionName']
            # Row is occasionally a list of up to 2 rows.  In that case, the seatNumbers will have repeated elements, ie:
            #  quantity=4
            #  rows=[1,2]
            #  seatNumbers=[5,6,5,6]
            rows = listing['row'].split(',')
            seatNumbers = listing.get('seatNumbers')
            quantity = listing['quantity']
            # For seatnumbers that are not specified, use list_id plus an index
            if len(rows) == 2:
                # Sort of awkward way of handling len(rows)==2, but... This will make searNumbers the right length
                if quantity % 2 == 0:
                    quantity = quantity // 2
                else:
                    raise SeatGroupError("Error adding SeatGroup - quantity of a two-row listing not an even number (section: {0}, rows: {1}, quantity: {2}".format(section, rows, quantity))

            for row in rows:
                if seatNumbers == "General Admission":
                    local_seatNumbers = ["{0}-GA{1}".format(list_id, i) for i in range(0, quantity)]
                elif seatNumbers is None:
                    local_seatNumbers = ["{0}-None{1}".format(list_id, i) for i in range(0, quantity)]
                else:
                    # Seat numbers can be NaN even if they're a comma separated list
                    seat_gen = mygen()
                    # Use only seatNumbers[:quantity] to avoid duplicate seats when we have a two-row case
                    local_seatNumbers = ["{0}-NaN{1}".format(list_id, next(seat_gen)) if x=="NaN" else x for x in seatNumbers.split(',')[:quantity]]

                for seatNumber in local_seatNumbers:
                    # print('DEBUG: Creating seat with Price: {0} (face: {4}), Loc: ({1}, {2}, {3})'.format(price, section, row, seatNumber, facevalue))
                    seat = Seat(price=price,
                                list_id=list_id,
                                facevalue=facevalue,
                                available=True,
                                )
                    # Some listing files have duplicate listings.  Handle these here and warn the user
                    loc = (section, row, seatNumber)
                    try:
                        sg.add(seat, loc)
                    except DuplicateSeatError:
                        print("WARNING: Duplicate seat detected at {0}".format(loc))
        return sg


class SeatGroupChronology(object):
    """
    Object for grouping many SeatGroups chronologically and extracting time-based data
    """
    def __init__(self):
        self.seatgroups = {}
        self.sorted_timepoints = []

    def add_seatgroup(self, timepoint, sg):
        """
        Add a SeatGroup to the object, checking if another of the same timepoint already exists.

        :param timepoint: datetime object identifying the SeatGroup (used as the key for storing data)
        :param sg: SeatGroup to be added
        :return: None
        """
        if timepoint in self.seatgroups:
            raise SeatGroupError("Cannot add SeatGroup at timepoint {0} - SeatGroup already exists with that timepoint".format(timepoint))
        else:
            if isinstance(timepoint, datetime.datetime):
                self.seatgroups[timepoint] = sg
                bisect.insort(self.sorted_timepoints, timepoint)
            else:
                raise SeatGroupError("Invalid timepoint {0} - must be a datetime object".format(timepoint))

    def add_seatgroups_from_event_json(self, timepoints, json_files):
        """
        Add a seatgroup from a list of JSON formatted even files and their timepoint identifiers.

        :param timepoints: See add_timepoint (simular version of this function)
        :param json_files: See add_timepoint (simular version of this function)
        :return: None
        """
        for timepoint, json_file in zip(timepoints, json_files):
            self.add_seatgroup_from_event_json(timepoint, json_file)

    def add_seatgroup_from_event_json(self, timepoint, json_file):
        """
        Add a SeatGroup from a JSON formatted event file, identified by a timepoint key.

        :param timepoint: See add_seatgroup.
        :param json_file: Filename of a JSON file with event listings data
        :return: None
        """
        print("DEBUG: Adding timepoint {0} from file {1}".format(timepoint, json_file))
        self.add_seatgroup(timepoint, SeatGroup.init_from_event_json(json_file))

    def find_differences(self):
        """
        Compares all timepoints chronologically to determine sales, adds, price changes, and listings changes over time.

        :return: None
        """
        added = SeatGroupChronology()
        removed = SeatGroupChronology()
        new_price = SeatGroupChronology()
        new_listid = SeatGroupChronology()
        for i in range(1, len(self.sorted_timepoints)):
            this_t = self.sorted_timepoints[i]
            prev_t = self.sorted_timepoints[i-1]
            print("comparing {0} to {1}".format(this_t, prev_t))
            diff = self.seatgroups[this_t].difference(self.seatgroups[prev_t])
            for k in sorted(diff):
                print('\t', k)
                diff[k].display()
            added.add_seatgroup(this_t, diff['added'])
            removed.add_seatgroup(this_t, diff['removed'])
            new_price.add_seatgroup(this_t, diff['new_price'])
            new_listid.add_seatgroup(this_t, diff['new_listid'])
        return {'added': added, 'removed': removed, 'new_price': new_price, 'new_listid': new_listid}

    def get_lens(self):
        """
        Return a numpy array with rows of (timepoint, len(SG@timepoint)).

        :return:
        """
        lens = [None] * len(self.sorted_timepoints)
        # lens = np.empty((len(self.sorted_timepoints), 2))

        for i, t in enumerate(self.sorted_timepoints):
            # lens[i, :] = (t, len(self.seatgroups[t]))
            lens[i] = (t, len(self.seatgroups[t]))
        return np.array(lens)

    def __getitem__(self, t, single_type='nearest'):
        """
        Get one or more elements of the SeatGroupChronology

        A single entry is returned as a SeatGroup, whereas a slice is returned as a new SGC

        Future: Interpret the step variable of the slice to return a series of SGC's with the slice.

        :param t: A single timepoint in datetime format or a slice object between two timepoints (inclusive).
        :param single_type: Type of search method for getting a single timepoint:
                                nearest: (default) return the timepoint nearest to t, with ties always going to the
                                         nearest timepoint to the left (before) t)
                                exact: return the timepoint exactly matching t, or raise a KeyError exception
                                left: return the timepoint that is nearest to t and before or equal to t.  Returns a
                                      KeyError if there is no timepoint meeting this criteria.
                                right: return the timepoint that is nearest to t and equal to or after t.  Returns a
                                       KeyError if there is no timepoint meeting this criteria.
        :return: A SeatGroup (single timepoint) or SeatGroupChronology (multiple timepoints)
        """
        if isinstance(t, slice):
            # Interpret slice
            start = bisect.bisect_left(self.sorted_timepoints, t.start)
            stop =  bisect.bisect_right(self.sorted_timepoints, t.stop)
            data = [(self.sorted_timepoints[i], self.seatgroups[self.sorted_timepoints[i]]) for i in range(start, stop)]
            sgc_new = SeatGroupChronology()
            for tp, sg in data:
                sgc_new.add_seatgroup(tp, sg)
            return sgc_new
        elif isinstance(t, datetime.datetime):
            # Interpret single timepoint
            if single_type == 'exact':
                t_ret = t
                # return self.seatgroups[t]
            elif single_type == 'nearest':
                # Find where t would insert into self.sorted_timepoints, then compare the deltas
                i = bisect.bisect_left(self.sorted_timepoints, t)
                if i == 0:
                    # Special case at the beginning
                    t_ret = self.sorted_timepoints[i]
                elif i == len(self.sorted_timepoints):
                    # Special case at the end
                    t_ret = self.sorted_timepoints[-1]
                else:
                    # All other cases
                    d_left = t - self.sorted_timepoints[i-1]
                    d_right = self.sorted_timepoints[i] - t
                    if d_left <= d_right:
                        t_ret = self.sorted_timepoints[i - 1]
                    else:
                        t_ret = self.sorted_timepoints[i]
            elif single_type == 'left':
                i = bisect.bisect_right(self.sorted_timepoints, t)
                if i == 0:
                    # Special case at the beginning
                    raise KeyError("No timepoint to the left of {0}".format(t))
                else:
                    t_ret = self.sorted_timepoints[i - 1]
            elif single_type == 'right':
                i = bisect.bisect_left(self.sorted_timepoints, t)
                if i == len(self.sorted_timepoints):
                    # Special case at the beginning
                    raise KeyError("No timepoint to the right of {0}".format(t))
                else:
                    t_ret = self.sorted_timepoints[i]
            # Return as a single row 2D array
            return np.array((t_ret, self.seatgroups[t_ret]))[None, :]

# Exceptions
class SeatGroupError(Exception):
    pass
class DuplicateSeatError(Exception):
    pass

# Helpers
def mygen(start=0, stop=100, inc=1):
    """A simple custom generator"""
    i = start
    while i < stop:
        yield i
        i += inc