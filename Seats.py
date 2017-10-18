import bisect
import copy
import datetime
import json
import re
from pprint import pprint

import numpy as np

from nearest import nearest_index, nearest_value


class Seat(object):
    """
    Object to hold data associated with a single seat
    """
    def __init__(self, price=None, available=None, facevalue=None, list_id=None, season_ticket_group=None):
        self._price = None
        self.price = price
        self._facevalue = None
        self.facevalue = facevalue
        self.available = available
        self._list_id = None
        self.list_id = list_id
        self.season_ticket_group = season_ticket_group
        # These are what are used in evaluating equality.  Put them up here so I don't forget to add_seat to the list
        # if we add_seat new attributes
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
        return "{0}(price={1}, group={2})".format(type(self).__name__, self.price, self.season_ticket_group)

    @property
    def price(self):
        return self._price

    @price.setter
    def price(self, price):
        if price is None:
            self._price = None
        else:
            self._price = float(price)

class SeatGroup(object):
    """
    Object to hold and interact with either a group of Seats or or SeatGroups
    """
    def __init__(self):
        self.seats = {}
        self.sorted_names = []
        self.meta = {}

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

    def __add__(self, other):
        """
        Perform arithmatic addition between self and other, using all elements in self and returning a new SeatGroup

        :param other: Another SeatGroup
        :return: A new SeatGroup
        """
        return self.math_operation(other, operation='add', seat_locs=None)


    def __sub__(self, other):
        """
        Perform arithmatic addition between self and other, using all elements in self and returning a new SeatGroup

        :param other: Another SeatGroup
        :return: A new SeatGroup
        """
        return self.math_operation(other, operation='sub', seat_locs=None)


    def math_operation(self, other, operation='add', seat_locs=None, preserve_unreferenced_seats=False, inplace=False):
        """
        Return a new SeatGroup populated by seats priced as the difference (self.seats[some_seat] - other).

        Other can be a fixed value (int, float, or Seat), or can be another SeatGroup.  If a SeatGroup, all seat_locs must be
        in both SeatGroups, else an exception is raised

        :param other: Either a fixed value (int, float, or Seat) or a SeatGroup
        :param seat_locs: Locations to include in differencing.
        :param preserve_unreferenced_seats:
            If True, returned SeatGroup also includes copies of all of self's seats not referenced in seat_locs (but
            only seats in seat_locs are modified by the subtraction)
            If False, returned SeatGroup includes only seats referenced in seat_locs.
        :param inplace: Does subtraction inplace instead of returning a copy
        :return: A SeatGroup
        """
        if seat_locs is None:
            seat_locs = self.get_locs()

        if preserve_unreferenced_seats:
            all_seat_locs = self.get_locs()
        else:
            all_seat_locs = seat_locs

        if inplace:
            raise NotImplementedError("Need to implement and think about concequences for inplace==True + preserve_unreferenced_seats==False")

        # If SeatGroup had any other data, this would be better served by a real .copy() method (maybe one that accepts
        # seat_locs to copy subsets).  But this works almost as well
        newsg = self.get_seats_as_seatgroup(seat_locs=all_seat_locs, copy_seats=True)

        # Make a list of other's seats needed here.
        # Try to use other as a SeatGroup, then as a Seat, then as a price
        try:
            other_seats = other.get_seats_as_list(seat_locs)
        except AttributeError:
            try:
                price = other.price
            except AttributeError:
                price = other
            other_seats = [Seat(price)] * len(seat_locs)

        seats = newsg.get_seats_as_list(seat_locs)

        for i in range(len(seats)):
            if operation == 'add':
                seats[i].price = seats[i].price + other_seats[i].price
            elif operation == 'sub':
                seats[i].price = seats[i].price - other_seats[i].price

        return newsg


    def subtract(self, other, seat_locs=None, preserve_unreferenced_seats=False, inplace=False):
        """
        Return a new SeatGroup populated by seats priced as the difference (self.seats[some_seat] - other).

        Other can be a fixed value (int, float, or Seat), or can be another SeatGroup.  If a SeatGroup, all seat_locs must be
        in both SeatGroups, else an exception is raised

        :param other: Either a fixed value (int, float, or Seat) or a SeatGroup
        :param seat_locs: Locations to include in differencing.
        :param preserve_unreferenced_seats:
            If True, returned SeatGroup also includes copies of all of self's seats not referenced in seat_locs (but
            only seats in seat_locs are modified by the subtraction)
            If False, returned SeatGroup includes only seats referenced in seat_locs.
        :param inplace: Does subtraction inplace instead of returning a copy
        :return: A SeatGroup
        """
        return self.math_operation(other, operation='sub', seat_locs=seat_locs,
                                   preserve_unreferenced_seats=preserve_unreferenced_seats, inplace=inplace)


    def add_seat(self, seat, name, make_deep_groups=True, merge=True):
        """
        Add a Seat ot SeatGroup to the object

        For added SeatGroups, optionally merge with existing SeatGroup when a SeatGroup of the same name already exists.

        :param seat:
        :param name:
        :param make_deep_groups: If True, if a seat is added to a SeatGroup that does not exist, that group will be
                                 created.  ie:
                                    sg = SeatGroup()
                                    sg.add_seat(some_seat, (rowA, seat1), make_deep_groups=True)
                                 Will create a seatgroup sg that has a nested seatgroup sg.seats['rowA'], where the
                                 nested group contains 'some_seat'
                                 If False, will raise an exception if all subgroups do not already exist.
        :param merge: Boolean for handling merging of SeatGroups.  If merge=True, seat is a SeatGroup, and name is
                      already in use (name in self.seats.keys()), attempt to merge the two SeatGroups.  Raise a
                      DuplicateSeatError if merger results in a conflict.
        :return: None
        """
        if not (isinstance(name, tuple) or isinstance(name, list)):
            raise SeatGroupError("Cannot add_seat Seat - invalid name.  Must be iterable, but got: {0}".format(name))
        else:
            # Seat being added has multi-level name.  Could be len=1 (this level), len>1 (deeper level).
            this_name = str(name[0])
            if len(name) == 1:
                # This is the level where the seat should be added
                if isinstance(seat, Seat):
                    if this_name in self.seats:
                        raise DuplicateSeatError("Seat \"{0}\" already in use".format(this_name))
                    else:
                        # Store the Seat and maintain a sorted list of names
                        bisect.insort(self.sorted_names, this_name)
                        self.seats[this_name] = seat
                elif isinstance(seat, SeatGroup):
                    if this_name in self.seats:
                        if merge:
                            self.seats[this_name].merge(seat, handle_duplicates=False, inplace=True)
                        else:
                            raise DuplicateSeatError("Seat \"{0}\" already in use".format(this_name))
                    else:
                        # Store the Seat and maintain a sorted list of names
                        bisect.insort(self.sorted_names, this_name)
                        self.seats[this_name] = seat
                else:
                    raise SeatGroupError(
                        "Seat '{0}' must be a Seat or SeatGroup object - found {1}".format(this_name, type(seat)))
                    # Note: This does not return, it continues below this if/else.  Flow is a little confusing, refactor?
            else:
                # Seat is added deeper than this group.  Check if it exists (and optionally create it), then recurse
                this_name = str(name[0])
                if not this_name in self.seats:
                    if make_deep_groups:
                        sg = SeatGroup()
                        self.add_seat(seat=sg, name=(this_name,))
                    else:
                        raise SeatGroupError("Cannot add_seat seat '{0}', SeatGroup '{1}' not defined".format(name, name[0]))
                self.seats[this_name].add_seat(seat, name[1:], make_deep_groups=make_deep_groups)
                return

    def remove(self, name, remove_deep_seats=True, cleanup_empty_groups=True):
        """
        Remove a Seat or SeatGroup from the object

        :param name: Name of the seat to be removed.  Can be a tuple describing a nested seat if remove_deep_seats
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

    def get_seats_as_seatgroup(self, seat_locs, fail_if_missing=True, copy_seats=False):
        """
        Return a SeatGroup of seats described by an iterable of seat location tuples.

        Structure of the original group is preserved (so if seats were broken into SeatGroups in the original SeatGroup,
        they are returned in a similar way in the new SeatGroup

        :param seat_locs:
        :param fail_if_missing: Raise exception if a seat in seat_locs does not exist
        :param copy_seats: If True, return copies of the seats instead of references
        :return:
        """
        seats_as_list = self.get_seats_as_list(seat_locs, fail_if_missing=fail_if_missing, copy_seats=copy_seats)
        seats = zip(seat_locs, seats_as_list)
        newsg = SeatGroup()
        for loc, seat in seats:
            if seat is None:
                continue
            else:
                newsg.add_seat(seat, loc)
        return newsg

    def get_seats_as_list(self, seat_locs, fail_if_missing=True, copy_seats=False):
        """
        Return a list of seats described by an iterable of seat location tuples

        :param seat_locs:
        :param fail_if_missing: Raise exception if a seat in seat_locs does not exist
        :param copy_seats: If True, return copies of the seats instead of references
        :return: List of seat objects
        """
        # TODO: Add wildcards, ie: loc=(section1, rowA, *)?  Or can this be covered by just get(loc=(section1, rowA)) then an action on that new group?
        returned = [None] * len(seat_locs)
        for i, loc in enumerate(seat_locs):
            if not (isinstance(loc, tuple) or isinstance(loc, list)):
                raise SeatGroupError("Invalid seat_loc - must be a list of tuples")
            elif len(loc) == 1:
                try:
                    # Locations are always strings
                    if copy_seats:
                        returned[i] = copy.deepcopy(self.seats[str(loc[0])])
                    else:
                        returned[i] = self.seats[str(loc[0])]
                except KeyError as e:
                    if fail_if_missing:
                        raise e
                    else:
                        # Redundant, but makes it really clear...
                        returned[i] = None
            else:
                try:
                    # Get will return a list of seats of length 1, but we just want the seat
                    returned[i] = self.seats[str(loc[0])].get_seats_as_list([loc[1:]])[0]
                except KeyError as e:
                    if fail_if_missing:
                        raise e
                    else:
                        returned[i] = None
                except AttributeError:
                    raise SeatGroupError("Seat '{0}' is a Seat but was used as a SeatGroup with location '{1}'".format(loc[0], loc))
        return returned

    def get_locs(self, seat_locs=None, depth=None):
        """
        Returns a list of tuples identifying all the seats in this SeatGroup, including seats nested in other SeatGroups

        Results returned in sorted order.
        :seat_locs: (I think) Subset of the SeatGroup to be searched
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

    def get_prices(self):
        """
        Return a numpy array of prices in the SG, including nested seats.  These are in the same order as get_locs.

        Future: There must be a better way to do this.  Concatenation for np.arrays is slow...
                Feels like I'm cramming numpy arrays into a life as a dynamic array..
                Non-recursive approach building a list then converting to np.array make more sense?
        Future: Should these always return the seat name with the price?  Other price-returning methods in SGC and
                elsewhere return a record array of [[timepoint, price], [timepoint, price]...] because the order is non-
                trivial (there could be some timepoints without any sales and thus no price is returned, or timepoints
                where multiple prices are returned).  Adopt same convention here?

        :return: A numpy array of prices, in the same order as get_locs()
        """
        prices = np.array(())
        for name in self.sorted_names:
            try:
                deep_prices = self.seats[name].get_prices()
                prices = np.concatenate((prices, deep_prices))
            except AttributeError:
                prices = np.concatenate((prices, np.array((self.seats[name].price,))))
        return prices


    def merge(self, other, inplace=False, handle_duplicates = False):
        """
        Merge two SeatGroups together, including nested Seats and SeatGroups, returning a new SeatGroup.

        Raises an exception if any duplicate seats are detected.

        :param other: Another SeatGroup
        :param inplace: Boolean.  Whether to merge to this object inplace or return a new SG
        :param handle_duplicates: If False, raises exception when duplicates detected.
                                  If self, always uses the seat from this SeatGroup when duplicates are found
                                  If other, always uses the seat from the other SeatGroup when duplicates are found
        :return: A new SeatGroup if inplace=False, else None
        """
        if handle_duplicates:
            raise NotImplementedError()
        else:
            # First check for duplicates
            locs_this = self.get_locs()
            locs_other = other.get_locs()

            locs_both = [loc for loc in locs_this if loc in locs_other]
            if len(locs_both) > 0:
                raise DuplicateSeatError("Found duplicate seats when merging: {0}".format(locs_both))
        if inplace:
            sg = self
        else:
            sg = self.get_seats_as_seatgroup(locs_this)
        merged_seats = zip(locs_other, other.get_seats_as_list(locs_other))
        for loc, seat in merged_seats:
            sg.add_seat(seat, loc)
        if not inplace:
            return sg

    def update_names(self, namemap=None, depth=None):
        """
        Update names of the nested SeatGroups and Seats based on namemap.

        :param namemap: List of tuples of (regex_formatted_pattern, repl)
        :param depth: Depth to which the names should be updated in the nested SeatGroups (depth = 1 renames only the
                      Seats/Groups in self.  depth = 2 renames self and the Seats/Groups one further level deep.
                      depth==None renames all nested items)
        :return: None
        """
        for name in self.sorted_names:
            # update names at deeper levels if requested (double if statment to handle depth=None.
            if isinstance(self.seats[name], SeatGroup):
                if depth is None:
                    go_deep = True
                elif depth > 1:
                    go_deep = True
                    depth = depth - 1
                else:
                    go_deep = False
                if go_deep:
                    self.seats[name].update_names(namemap=namemap, depth=depth)

            # Find all names that match criteria at this level and rename them and/or merge with existing SeatGroups
            for pattern, repl in namemap:
                # print("Running search to replace {0} with {1}".format(pattern, repl))
                pat_comp = re.compile(pattern)
                to_replace = []
                # First build list of items needing replacing, then do actual replacement.  Combining these would change
                # the order/placement in sorted_names.
                for name in self.sorted_names:
                    match = pat_comp.search(name)
                    if match:
                        # print("SG.update_names: Found {0} in {1}, adding to to_replace queue".format(pattern, name))
                        to_replace.append((name, pat_comp.sub(repl, name)))
                # Perform renames
                for oldname, newname in to_replace:
                    # print("SG.update_names: Changing \"{0}\" to \"{2}\" in {1}".format(pattern, name, repl))
                    # print("\tChanging {0} with {1}".format(oldname, newname))
                    temp = self.seats[oldname]
                    # print("got temp: ", temp)
                    self.remove((oldname,))
                    self.add_seat(temp, (newname,))

    def difference(self, other_sg):
        """
        Find the differences between this and other_sg and return them.

        TODO: Break this down into difference_added(), difference_new_price(), ..., so you don't call them all at once unnecessarily.  Have difference() call the others, and have everything accept an optional all_locs which will force the func to only consider a subset of seats

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
                res['removed'].add_seat(other_seat, loc)
            elif other_seat is None:
                # Added seat
                res['added'].add_seat(this_seat, loc)
            else:
                # Could be more than one of these at a time
                if this_seat.price != other_seat.price:
                    # Price change
                    res['new_price'].add_seat(this_seat, loc)
                if this_seat.list_id != other_seat.list_id:
                    # Listid change (new listing)
                    res['new_listid'].add_seat(this_seat, loc)

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
    def init_from_event_json(cls, json_file, get_meta=True):
        """
        Populate and return a SeatGroup object fro4m a JSON formatted event file

        :param json_file: Filename of a JSON file with event listings data
        :param get_meta: If True, will attempt to scrape metadata from the JSON (otherwise, data set to None)
        :return: None
        """
        # Load event information to dictionary
        with open(json_file, 'r') as f:
            event_dict = json.load(f)

        sg = cls()
        # Try to grab metadata
        try:
            sg.meta['opponent'] = event_dict['event_info']['eventMeta']['secondaryAct']
        except:
            pass
        try:
            date_format = "%Y-%m-%dT%H:%M:%S"
            temp = re.sub(r'[+\-]\d\d\:\d\d$', '', event_dict['event_info']['eventDateLocal'])
            sg.meta['date'] = datetime.datetime.strptime(temp, date_format)
        except:
            pass
        # Grab all listing data
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
                        sg.add_seat(seat, loc)
                    except DuplicateSeatError:
                        print("WARNING: Duplicate seat detected at {0}".format(loc))
        return sg


class SeatGroupFixedPrice(SeatGroup):
    """
    SeatGroup-like object that contains only a single seat and returns that seat whenever any seat name is requested.
    """
    def __init__(self):
        super().__init__()
        self.master_seat_name = ('*',)

    def add_seat(self, seat, *args, **kwargs):
        """
        Add the seat provided to the single named seat "*" using SeatGroup.add()
        :param seat:
        :param name:
        :param make_deep_groups:
        :param merge:
        :return:
        """
        super().add_seat(seat, self.master_seat_name, *args, **kwargs)

    def get_seats_as_list(self, seat_locs, fail_if_missing=True):
        """
        Mimic SeatGroup's function by returning a list of Seats of length len(seat_locs), but all elements reference .seats['*"]

        :param seat_locs:
        :param fail_if_missing: Ignored (here only for matching parent's signature
        :return: List of references to .seats["*"] of length len(seat_locs)
        """
        return [self.seats[self.master_seat_name[0]]] * len(seat_locs)


class SeatGroupChronology(object):
    """
    Object for grouping many SeatGroups chronologically and extracting time-based data
    """
    def __init__(self):
        self.seatgroups = {}
        self.sorted_timepoints = []
        self.meta = None # For things like home/away team, etc.

    def display(self):
        for tp in self.sorted_timepoints:
            print(tp)
            self.seatgroups[tp].display()

    def add_seatgroup(self, timepoint, sg, update_names=None, update_meta=True):
        """
        Add a SeatGroup to the object, checking if another of the same timepoint already exists.

        :param timepoint: datetime object identifying the SeatGroup (used as the key for storing data)
        :param sg: SeatGroup to be added
        :param update_names: If not None, invokes sg.update_names(update_names) to update any Seat names in the
                             SeatGroup.  Useful for data munging.
        :return: None
        """
        if timepoint in self.seatgroups:
            raise DuplicateSeatError("Cannot add_seat SeatGroup at timepoint {0} - SeatGroup already exists with that timepoint".format(timepoint))
        else:
            if isinstance(timepoint, datetime.datetime):
                self.seatgroups[timepoint] = sg
                if update_names is not None:
                    self.seatgroups[timepoint].update_names(update_names)
                bisect.insort(self.sorted_timepoints, timepoint)
                # Check the metadata
                if update_meta:
                    if self.meta != None and self.meta != self.seatgroups[timepoint].meta:
                        print("WARNING: Seatgroup metadata '{0}' does not match past metadata '{1}'.  Metadata updated with most recent data".format(self.seatgroups[timepoint].meta, self.meta))
                    self.meta = self.seatgroups[timepoint].meta
            else:
                raise SeatGroupError("Invalid timepoint {0} - must be a datetime object".format(timepoint))

    def add_seatgroups_from_event_json(self, timepoints, json_files, update_names=None):
        """
        Add a seatgroup from a list of JSON formatted even files and their timepoint identifiers.

        :param timepoints: See add_timepoint (similar version of this function)
        :param json_files: See add_timepoint (similar version of this function)
        :return: None
        """
        for timepoint, json_file in zip(timepoints, json_files):
            self.add_seatgroup_from_event_json(timepoint, json_file, update_names=update_names)

    def add_seatgroup_from_event_json(self, timepoint, json_file, update_names=None):
        """
        Add a SeatGroup from a JSON formatted event file, identified by a timepoint key.

        :param timepoint: See add_seatgroup.
        :param json_file: Filename of a JSON file with event listings data
        :return: None
        """
        print("DEBUG: Adding timepoint {0} from file {1}".format(timepoint, json_file))
        self.add_seatgroup(timepoint, SeatGroup.init_from_event_json(json_file), update_names=update_names)

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
            # print("comparing {0} to {1}".format(this_t, prev_t))
            diff = self.seatgroups[this_t].difference(self.seatgroups[prev_t])
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

    def get_prices(self, f=np.min, return_type='numpy'):
        """

        Future: Merge all price_type scalar options into the same returned numpy record array?  Would save computation,
                but mess with the sgc return type option (multiple entries with min, max, avg in a SGC would be
                impossible to use).

        :param f:   Function to be applied to the prices returned for each timepoint's SeatGroup.  Default is np.min to
                    return minimum seat price in the SG, but could be np.max, np.average, or None (to return all prices)
                    Note: This function is only appled if len(prices) returned from the SG is greater than zero.
        :param return_type: Type of data to be returned:
                                numpy: a numpy record array with columns of timepoint and price (note that if
                                       f==None, each price is returned in a separate row (thus timepoint may
                                       not be unique)), ie if timepoint1 has two seats with prices price1a and price1b:
                                        return = [[timepoint1, price1a], [timepoint1, price1b]]
                                (not implemented) sgc: a SGC that includes dummy seats with the requested price_type (redundant if
                                     price_type=='all')
        :return:
        """
        if return_type == 'sgc':
            raise NotImplementedError("...")
        elif return_type == 'numpy':
            # Is there a good way to avoid dynamically allocating the array here?  You might have 0, 1, or many entries for
            # each timepoint...
            data = []

            for tp in self.sorted_timepoints:
                prices = self.seatgroups[tp].get_prices()

                if f is not None and len(prices) > 0:
                    prices = f(prices)
                data.append((tp, prices))

            # Flatten the data if needed
            # I think this way dynamically allocates the array during flattening, but couldn't think of how to do it easily
            # without dynamic allocation
            data = [(label, el) for label, sublst in data
                                  for el in (sublst if hasattr(sublst, "__iter__") else [sublst])]

            # Convert to np record array
            # Used general object here instead of datetime64 because matplotlib recognizes datetime but not datetime64
            data = np.rec.array(data,
                                # dtype=[('timepoint', 'datetime64[us]'), ('price', 'float')])
                                dtype=[('timepoint', 'O'), ('price', 'float')])
        else:
            raise ValueError("Invalid return type \"{0}\"".format(return_type))
        return data

    def __add__(self, other):
        """
        Convenience function to apply the SeatGroup.math_operation('add') to all SeatGroups in the chronology, using other.

        :param other: Another SeatGroup
        :return: A new SeatGroup
        """
        return self.math_operation(other, operation='add', seat_locs=None, inplace=False)

    def __sub__(self, other):
        """
        Convenience function to apply the SeatGroup.math_operation('sub') to all SeatGroups in the chronology, using other.

        :param other: Another SeatGroup
        :return: A new SeatGroup
        """
        return self.math_operation(other, operation='sub', seat_locs=None, inplace=False)

    def math_operation(self, other, operation='add', seat_locs=None, preserve_unreferenced_seats=False, inplace=False):
        """
        Convenience function to apply the SeatGroup.math_operation to all SeatGroups in the chronology, using other.

        :param other: The other SeatGroup in the operation
        :param operation:
        :param seat_locs:
        :param preserve_unreferenced_seats:
        :param inplace:
        :return: None
        """

        if inplace:
            new_sgc = self
        else:
            new_sgc = copy.deepcopy(self)
        for tp in new_sgc.sorted_timepoints:
            new_sgc.seatgroups[tp].math_operation(other, operation=operation, seat_locs=seat_locs,
                                               preserve_unreferenced_seats=preserve_unreferenced_seats, inplace=inplace)
        return new_sgc

    def __getitem__(self, t, single_type='nearest'):
        """
        Get one or more elements of the SeatGroupChronology

        A single entry is returned as a SeatGroup, whereas a slice is returned as a new SGC

        Future: Interpret the step variable of the slice to return a series of SGC's with the slice.
        Future: Make companion get that returns just the timepoint that meets the single get criteria (that way you can
                know which SeatGroup you got dring single gets)
        :param t: A single timepoint in datetime format or a slice object between two timepoints (inclusive).
                  If a slice object:
                    if slice.step==None, return all timepoints between slice.start and slice.stop.
                    if slice.step!=None, return some timepoints using self.arange(start, stop, step) (note
                    default value of rename_timepoint)
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
        if isinstance(t, datetime.datetime):
            # Single timepoint, return single seatgroup
            t_nearest = self.get_timepoint(t, single_type=single_type)
            return copy.deepcopy(self.seatgroups[t_nearest])
        else:
            return self.get_timepoints_as_seatgroupchronology(dt_slice=t)

    def get_timepoint(self, t, single_type='nearest'):
        """
        Return a the timepoint datetime object in the SeatGroupChronology nearest to t

        :param t: A datetime object
        :param single_type: Mode to assess nearest timepoint:
                                exact: (Kind of useless... but a binding to check if something is in the SGC) Returns
                                       a timepoint if the t exactly matches a timepoint in the SGC, otherwise raises a
                                       SeatGroupError exception
                                nearest: Returns the timepoint in the SGC nearest to t
                                left: Returns the timepoint in the SGC nearest and chronologically before t, or raises
                                a SeatGroupError exception.
                                right: Returns the timepoint in the SGC nearest and chronologically after t, or raises
                                a SeatGroupError exception.
        :return: a single timepoint or a list of timepoints (the datetime objects)
        """

        # Interpret single timepoint.  Not sure why I'd actually use exact, but still...  Guess it is a sort of
        # safe and similarly API'd validation method?
        if single_type == 'exact':
            if t in self.sorted_timepoints:
                t_ret = t
            else:
                raise SeatGroupError("Timepoint {0} not in SeatGroupChronology".format(t))
        elif single_type == 'nearest':
            t_ret = nearest_value(self.sorted_timepoints, t)
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
        return t_ret

    def get_timepoints(self, dt_slice):
        """
        Returns a slice of timepoints from the SGC in a sorted list, including all or evenly spaced timepoints in that range.

        :param dt_slice: A slice object with optionally any of start (datetime object), stop (datetime), and step
                         (timedelta)
                         start and stop: datetime objects specifying the range of dates to return (only dates between
                                         these are returned).  If either is None, the range returned will extend to the
                                         respective end of the original list of timepoints
                         step: the approximate spacing at which to return a subset of the results (note this is
                               approximate because it is highly unlikely that the data is perfectly spaced, so the
                               nearest timepoint between start and stop will be returned for each step.
                               If None, all data within the range is returned.
                               NOTE: Step can be negative, so long as start > stop
        :return: A sorted list of datetime objects
        """
        return dt_list_arange(self.sorted_timepoints, dt_slice)

    def get_timepoints_as_seatgroupchronology(self, dt_slice):
        """
        Returns a slice of timepoints from the SGC in new SGC, including all or evenly spaced timepoints in that range.

        :param dt_slice: A slice object with optionally any of start (datetime object), stop (datetime), and step
                         (timedelta)
                         start and stop: datetime objects specifying the range of dates to return (only dates between
                                         these are returned).  If either is None, the range returned will extend to the
                                         respective end of the original list of timepoints
                         step: the approximate spacing at which to return a subset of the results (note this is
                               approximate because it is highly unlikely that the data is perfectly spaced, so the
                               nearest timepoint between start and stop will be returned for each step.
                               If None, all data within the range is returned.
                               NOTE: Step can be negative, so long as start > stop
        :return: A SeatGroupChronology instance
        """
        timepoints = self.get_timepoints(dt_slice)
        sgc_new = SeatGroupChronology()
        for tp in timepoints:
            sgc_new.add_seatgroup(tp, copy.deepcopy(self.seatgroups[tp]))
        return sgc_new

    def get_seats(self, seat_locs):
        """
        Return a new SGC that contains data for all timepoints but only at the specified seat locations.

        NOTE: Why is this not .get_seats?  Isn't this like the other .get_seats functions?

        :param seat_locs: List of location tuples of the format required by SeatGroup.get_seats_as_seatgroup()
        :return: SeatGroupChronology type object
        """
        sgc = SeatGroupChronology()
        for tp in self.sorted_timepoints:
            sg = self.seatgroups[tp].get_seats_as_seatgroup(seat_locs, fail_if_missing=False)
            sgc.add_seatgroup(tp, sg)
        return sgc

    def get_locs(self, seat_locs=None, depth=None):
        """
        Returns a list of tuples identifying all the seats in any SeatGroup within this Chronology.

        :param seat_locs:
        :param depth:
        :return:
        """
        all_locs = set()
        for tp in self.sorted_timepoints:
            all_locs.update(self.seatgroups[tp].get_locs(seat_locs=seat_locs, depth=depth))
        return list(sorted(all_locs))

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

# These datetime list functions could be wrapped into a datetime list object.  Could still be interacted with like a
# (maybe a subclass of list?) but with these additional features
def dt_list_trim(dt_list, dt_slice):
    """
    Trim a sorted list of datetime instances slice to include only datetimes within a range

    :param dt_slice: A slice object with optionally any of start (datetime object) and stop (datetime):
                     start and stop: datetime objects specifying the range of dates to return (only dates between
                                     these are returned).  If either is None, the range returned will extend to the
                                     respective end of the original list of timepoints
                     step: Only used to denote the direction or marching between start and stop.  If step > 0, start
                           must be chronologically before stop.  If step < 0, start can be chronologically after stop
        :return: A sorted list of datetime objects
    """
    # Make start <= stop
    if dt_slice.step is None or dt_slice.step.total_seconds() >= 0:
        start = dt_slice.start
        stop = dt_slice.stop
    else:
        start = dt_slice.stop
        stop = dt_slice.start

    # Get the indices bounding the slice of the timepoint list
    if start is None:
        start = 0
    else:
        i = bisect.bisect_left(dt_list, start)
        # Ensure the returned timepoint is inside the range, not just outside
        if dt_list[i] < start:
            start = i + 1
        else:
            start = i
    if stop is None:
        stop = None
    else:
        i = bisect.bisect_right(dt_list, stop)
        # Ensure the returned timepoint is inside the range, not just outside
        if dt_list[i] > stop:
            stop = i - 1
        else:
            stop = i
        # stop = bisect.bisect_right(dt_list, stop)

    # deepcopy seems messy here, but I want to make sure I'm not returning a view of anything...
    if start == stop:
        new_list = [copy.deepcopy(dt_list[start])]
    else:
        new_list = copy.deepcopy(dt_list[start:stop])
    return new_list

def dt_list_arange(dt_list, dt_slice):
    """
    Return a subset of a list of datetime instances.

    The returned list has elements with datetimes in the range from dt_slice.start to dt_slice.stop at approximately
    dt_slice.step increments.  If start or stop are None, the datetime at the respective end of the lists will be used.

    :param dt_list: A sorted list of datetime object
    :param dt_slice: A slice object with at least step specified as a timedelta object, and optionally start and/or
                     stop specified as datetime objects to bound the returned subset.  If start or stop are None, data
                     will be returned to the respective end of the list.
                     If step is negative, start represents the last item chronologically and stop the first
    :return: A sorted list of datetime objects within the range of start and stop spaced approximately step increments
             apart.
    """
    if dt_slice.step is None:
        raise ValueError ("step must be defined - value is None")
    # Get only the relevant portion of the dt_list
    dt_list = dt_list_trim(dt_list, dt_slice)

    # Starting position for the search for either direction(this will always be the first search index)
    if dt_slice.step.total_seconds() > 0:
        i = 0
    else:
        i = len(dt_list) -1
    if dt_slice.start is None:
        dt_target = copy.deepcopy(dt_list[i])
    else:
        dt_target = dt_slice.start

    indices = set()
    indices.add(i)

    while True:
        dt_target = dt_target + dt_slice.step
        if dt_target < dt_list[0] or dt_target > dt_list[-1]:
            break
        i = nearest_index(dt_list, dt_target)
        # i = bisect.bisect_left(dt_list, dt_target)
        indices.add(i)

    dt_list = sorted([copy.deepcopy(dt_list[i]) for i in indices])
    return dt_list