from Seats import DuplicateSeatError, SeatGroupError, SeatGroup, Seat
import json

class Event(object):
    """
    Object for a event such as a game or concert.
    """
    def __init__(self):
        self.chronology = {}
        self.datetime = None
        self.location = None
        self.meta = {} # For things like home/away team, etc.

    def add_meta(self, json_file):
        """
        Add an Event's metadata from a JSON formatted event file.
        :param json_file:
        :return:
        """
        # Should there be a non-JSON way to do this too?  Maybe this is dict based and then the JSON one loads and
        # formats to a standard dict?
        raise NotImplementedError()

    def add_timepoint(self, datetime, json_file):
        """
        Add an Event timepoint from a JSON formatted event file.

        :param json_file:
        :return:
        """
        print("DEBUG: Adding timepoint {0} from file {1}".format(datetime, json_file))
        # Load event information to dictionary
        with open(json_file, 'r') as f:
            event_dict = json.load(f)

        sg = SeatGroup()
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
                    raise EventError("Error adding timepoint - quantity of a two-row listing not an even number (section: {0}, rows: {1}, quantity: {2}".format(section, rows, quantity))

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
                    print('DEBUG: Creating seat with Price: {0} (face: {4}), Loc: ({1}, {2}, {3})'.format(price, section, row, seatNumber, facevalue))
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
            self.chronology[datetime] = sg


    # Properties
    # Add day_of_week property?
    # Add time of event/date of event, which pulls from the self.datetime?

# Exceptions
def EventError(Exception):
    pass

# Helper
def mygen(start=0, stop=100, inc=1):
    """A simple custom generator"""
    i = start
    while i < stop:
        yield i
        i += inc