from pprint import pprint
import bisect

class Seat(object):
    """
    Object to hold data associated with a single seat
    """
    def __init__(self, price=None, available=None):
        self.price = price
        self.available = available


    def __repr__(self):
        return "{0}(price={1}, available={2})".format(type(self).__name__, self.price, self.available)


class SeatGroup(object):
    """
    Object to hold and interact with either a group of Seats or or SeatGroups
    """
    def __init__(self):
        self.seats = {}
        self.sorted_names = []

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
                raise SeatGroupError("Seat \"{0}\" already in use".format(name))
            else:
                # Store the Seat and maintain a sorted list of names
                bisect.insort(self.sorted_names, name)
                self.seats[name] = seat
        else:
            raise SeatGroupError("Seat '{0}' must be a Seat or SeatGroup object - found {1}".format(name, type(seat)))

    def remove(self, name):
        """
        Remove a Seat of SeatGroup from the object

        :param name:
        :return: None
        """
        # Internally, names are always treated as strings
        name = str(name)

        try:
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
        seats = zip(seat_locs, self.get_seats_as_list(seat_locs))
        newsg = SeatGroup()
        for loc, seat in seats:
            newsg.add(seat, loc)
        return newsg

    def get_seats_as_list(self, seat_locs):
        """
        Return a list of seats described by an iterable of seat location tuples

        :param seat_loc:
        :return: List of seat objects
        """
        # TODO: Add wildcards, ie: loc=(section1, rowA, *)?  Or can this be covered by just get(loc=(section1, rowA)) then an action on that new group?
        returned = [None] * len(seat_locs)
        for i, loc in enumerate(seat_locs):
            if len(loc) == 1:
                returned[i] = self.seats[loc[0]]
            else:
                try:
                    # Get will return a list of seats of length 1, but we just want the seat
                    returned[i] = self.seats[loc[0]].get_seats_as_list([loc[1:]])[0]
                except AttributeError:
                    raise SeatGroupError("Seat '{0}' is a Seat but was used as a SeatGroup with location '{1}'".format(loc[0], loc))
        return returned

    def get_locs(self):
        """
        Returns a list of tuples identifying all the seats in this SeatGroup, including seats nested in other SeatGroups
        :return:
        """
        seat_list = []
        for seat in self.sorted_names:
            try:
                seats = self.seats[seat].get_locs()
                seat_list.extend([(seat, *s) for s in seats])
            except AttributeError:
                # This is a base level seat and does not need to be handled recursively
                seat_list.append((seat,))
        return seat_list


# Exceptions
class SeatGroupError(Exception):
    pass