import base64
import requests
import json
from pprint import pprint
import time
import gzip


class StubHub_API_Request(object):
    """
    Class to handle all actual http interactions with StubHub API
    """
    # Counter for all requests (this way we can easily see how many have occurred)
    i = 0
    # List holder for recent requests (list of times for the req_limit most recent requests)
    recent_req = []
    # The number of requests to limit of a given time
    req_limit_time = 60 # seconds
    req_limit = 10

    # Number of times to retry a request attempt that fails during the request call (applies to things like errors
    # from the requests package due to timeout, NOT responses from the Stubhub API that indicate errors)
    req_attempts_limit = 10

    @classmethod
    def canireq(cls):
        if len(cls.recent_req) < cls.req_limit:
            return True
        else:
            now = time.time()
            cls.recent_req = [req for req in cls.recent_req if ((now - req) < cls.req_limit_time)]
            if len(cls.recent_req) < cls.req_limit:
                return True
            else:
                return False

    @classmethod
    def request(cls, method, url, wait=True, verbose=True, warnfile='warnings.log', **kwargs):
        while True:
            now = time.time()
            if cls.canireq():
                # Try to make the request, catching and retrying on a requests ConnectionError
                # Do not validate the data, just validate that the request got a response at all
                req_attempts = 0
                while req_attempts < cls.req_attempts_limit:
                    req_attempts += 1
                    try:
                        if method=='get':
                            r = requests.get(url, **kwargs)
                        elif method=='post':
                            r = requests.post(url, **kwargs)
                        # If this all worked, break from the while loop (skipping the below else statement)
                        break
                    except requests.ConnectionError as e:
                        # If we found an error we know, log a warning and repeat
                        warn("Warning: Caught and handled connection error: {0}".format(e))
                        warn("\tRequest details: {0}, {1}".format(url, kwargs))
                else:
                    # If max attempts reached, raise an error
                    raise StubHub_API_Request_Error("Attempted request failed - max attempts reached ({0})".format(cls.req_attempts_limit))
                # Log the recent successful request at the current time
                cls.recent_req.append(now)
                cls.i += 1
                # Do some validation.  For now really basic, but could catch and repeat on a "too many recent requests" error (if there is one)
                if r.status_code == 200:
                    return r
                else:
                    raise StubHub_API_Request_Error("Request returned with status code \"{0}\"".format(r.status_code))
            if wait:
                # Wait the amount of time you think you need to (could be wrong if other requests happen between now and
                # then, but a good first guess)
                waittime = int(cls.recent_req[0] + cls.req_limit_time - now) + 1
                if verbose:
                    print("Too many recent requests - sleeping {0} seconds before trying again".format(waittime))
                time.sleep(waittime)
            else:
                raise StubHub_API_Request_Error("Too many recent requests - did not submit a request")



class StubHub_API(object):
    CONTENT_TYPE = 'application/x-www-form-urlencoded'
    API_URL_PRODUCTION = 'https://api.stubhub.com'
    API_URL_SANDBOX = 'https://api.stubhubsandbox.com'
    LOGIN_URL = '/login'
    INVENTORY_SEARCH_V2_URL = '/search/inventory/v2'
    EVENT_INFORMATION_V2_URL = '/catalog/events/v2'
    EVENT_SEARCH_V3_URL = '/search/catalog/events/v3'
    JSON_FORMAT = {'sort_keys':True, 'indent':4, 'separators':(',', ': ')}

    def __init__(self):
        self.c_key = None
        self.c_secret = None
        self.username = None
        self.password = None
        self.access_token = None
        self.expires_in = None
        self.refresh_token = None
        self.scope = None

    def set_login_info(self, loginfile=None):
        """
        Store login info (username, password, key, and secret) from a JSON file or dictionary.

        :param loginfile: (Optional) If string, denotes the name of a JSON formatted file with username, password, key, and
                          secret.
                          If dictionary, includes entries for username, password, key, and secret
                          If None, function will prompt user for username, password, key, and secret.
        :return: None
        """
        if loginfile is None:
            raise NotImplementedError("get_credentials not yet implemented for user-input login/password/key/secret")
        elif isinstance(loginfile, str):
            with open(loginfile, 'r') as f:
                loginfile = json.load(f)
        elif isinstance(loginfile, dict):
            # Interact with it the same as the json file below
            pass
        else:
            raise ValueError("Invalid value for loginfile: " + loginfile)
        self.c_key = loginfile['c_key']
        self.c_secret = loginfile['c_secret']
        self.username = loginfile['username']
        self.password = loginfile['password']


    def get_credentials(self):
        """
        Get login credentials (access_token and other info) from StubHub Login API, store, and return as dict

        Requires login info and scope to be set.

        :return:          A dictionary including:
                "access_token":
                "expires_in":
                "refresh_token":
                "scope":
                "token_type":
        """
        # base64 takes 8-bit binary byte data, not a string object.  Use .encode to convert this.
        # https://stackoverflow.com/questions/8908287/base64-encoding-in-python-3
        token_unencoded = self.c_key + ":" + self.c_secret
        token = base64.b64encode(token_unencoded.encode('utf-8'))

        print("Submitting login request with token (unencoded): {0}".format(token_unencoded))
        print("Submitting login request with token (encoded)  : {0}".format(token))

        # Login Request via POST to API
        # Not 100% sure what this extra decode is needed for
        headers = {'Content-Type': self.CONTENT_TYPE,
                   'Authorization': 'Basic ' + token.decode('utf-8')}
        data = {
            'grant_type': 'password',
            'username': self.username,
            'password': self.password,
            'scope': self.scope
        }

        r = StubHub_API_Request.request('post', self.url_login, headers=headers, data=data)

        # Save important credential information internally
        self.access_token = r.json()['access_token']
        self.expires_in = r.json()['expires_in']
        self.refresh_token = r.json()['refresh_token']

        # Return full credential info in dictionary json format
        return r.json()

    def store_credentials(self, file="credentials_prod.json"):
        """
        Get login credentials (access_token and other info) from StubHub Login API and store to class and a JSON file.

        Requires login info and scope to be set.

        :param file: Either a string denoting a file with JSON formatted credentials, or a dictionary
                     to be validated as credentials
        :return: None
        """
        cred = self.get_credentials()
        with open(file, 'w') as f:
            json.dump(cred, f, **self.JSON_FORMAT)

    def load_credentials(self, file="credentials_prod.json"):
        """
        Load Stubhub login credentials from a JSON formatted file into object.

        :param file: Either a string denoting a file with JSON formatted credentials, or a dictionary
                     to be validated as credentials
        :return: None
        """
        with open(file, 'r') as f:
            file = json.load(f)

        # Check for correct entries
        cred_keys = ["access_token", "expires_in", "refresh_token", "scope", "token_type"]
        for k in cred_keys:
            if k not in file:
                raise ValueError("Credentials missing key {0}".format(k))

        self.access_token = file['access_token']
        self.expires_in = file['expires_in']
        self.refresh_token = file['refresh_token']


    def search_events(self, query, city=None, rows=500, parking=False):
        """
        Search for events based on a query with optional city and return a dict of results.

        Could be expanded to use more of the API's features (finer search criteria).  See:
        https://developer.stubhub.com/store/site/pages/doc-viewer.jag?category=Search&api=EventSearchAPI&endpoint=searchforeventsv3&version=v3

        :param query: Any terms to search by (eg: "Carolina Panthers")
        :param city: City field in the search API
        :param rows: Number of results to return (max is 500)
        :param parking: Include parking listings in search results
        :return: Dict of results
        """
        params = {
            'q': query,
            'city': city,
            'sort': 'eventDateLocal asc',
            'rows': rows,
            'parking': parking,
        }
        events = StubHub_API_Request.request('get', url=self.url_event_search, headers=self.standard_headers,
                                             params=params, wait=True).json()
        return events


    def store_searched_events(self, filename = None, **kwargs):
        """
        Store all events found in an event search to file in JSON

        :param filename: File to store data to
        :return: None
        """
        events = self.search_events(**kwargs)
        with open(filename, 'w') as f:
            json.dump(events, f, **self.JSON_FORMAT)

    def get_event_info(self, eventid):
        """
        Get all information for an event and return as a dict

        :param eventid:
        :return: Dict of event information
        """
        # print("Getting info for event \"{0}\"".format(eventid))
        url = self.url_event_information + "/" + str(eventid)
        # print("url: ", url)
        info = StubHub_API_Request.request('get', url=url, headers=self.standard_headers, wait=True).json()
        return info


    def get_event_inventory(self, eventid, max_requests = 100, event_info='try', warnfile='warnings.log'):
        """
        Get all listings from an event and return as a dict.

        :param eventid: Event ID for the event requested
        :param event_info: If True, append information from the event to the returned dictionary
                           If "try", attempt to get the info but handle the exception and print a warning if it does
                           not succeed
        :return: Dict of event listings (including pricing and other summaries)
        """
        params = {
            'eventid': eventid,
            'rows': 250,
            'start': 0,
            'zonestats': 'true',
            'sectionstats': 'true',
            'pricingsummary': 'true',
        }

        # Perform first inventory get
        i = 1
        def safe_get():
            try:
                inv = StubHub_API_Request.request('get', self.url_inventory_search, headers=self.standard_headers, params=params, wait=True).json()
            except StubHub_API_Request_Error as e:
                warn("Warning: During get_event_inventory() caught StubHub_API_Request_Error \"{0}\".  No results returned.".format(e), warnfile)
                raise GetListingsError("Error in StubHub_API_Request during listings access for event {0}.  Caught exception \"{1}\"".format(eventid, e))
            return inv

        inv = safe_get()
        print("get {2}: retrieved {0}/{1} listings".format(len(inv['listing']), inv['totalListings'], 1))
        # Loop through until you have all listings, appending the listing key of the return to the original inv
        # (all other returns, except for start, will be the same)
        while i < max_requests and len(inv['listing']) < inv['totalListings']:
            i += 1
            params['start'] = len(inv['listing'])
            this_inv = safe_get()
            try:
                inv['listing'] = inv['listing'] + this_inv['listing']
                print("get {2}: retrieved {0}/{1} listings".format(len(inv['listing']), inv['totalListings'], i))
            except KeyError as e:
                # TODO: This is a stopgap.  I think I've got a case where sometimes I request exactly the last index and then it returns an inventory without listings.  For now, use a general catch here..
                warn("Warning: Got KeyError when accessing listings - no new inventory data accessed.  Problem with indexing on request?", warnfile)

        # Append event info to the inventory dict (nice to have it all in one place for later)
        if event_info:
            try:
                inv['event_info'] = self.get_event_info(eventid)
            except StubHub_API_Request_Error as e:
                if event_info == 'try':
                    # event info is a nice to have, not a need to have.  Let this one slide...
                    warn("Warning: Event info for {0} could not be accessed".format(eventid), warnfile)
                else:
                    raise e

        # Right now I'm only returning inv rather than storing in this class.  Does that make sense?
        # This class is more for interacting with the StubHub API, and not about formatting the data I get from it.
        return inv


    def store_event_inventory(self, filename = None, eventid = None, file_format='txt', warnfile='warnings.log'):
        """
        Store all listings from an event to a file in JSON

        See ref for information on read/write json to gzip:
        https://stackoverflow.com/questions/39450065/python-3-read-write-compressed-json-objects-from-to-gzip-file
        
        :param filename: File to store data to
        :param eventid: Event ID for the event requested
        :file_format: Format for the saved file:
                        txt: regular text file
                        gzip: binary gzip file using gzip package
        :return: Dict of event listings (including pricing and other summaries)
        """
        try:
            event_inventory = self.get_event_inventory(eventid=eventid, warnfile=warnfile)
        except GetListingsError as e:
            warn("Warning: store_event_inventory caught GetListingsError while accessing data for event {0}.  No data saved".format(eventid), warnfile)
            raise GetListingsError("Error storing event listings - could not pull inventory from StubHub")

        if file_format == 'txt':
            with open(filename, 'w') as f:
                json.dump(event_inventory, f, **self.JSON_FORMAT)
        elif file_format == 'gzip':
            with gzip.GzipFile(filename, 'w') as f:
                json_str = json.dumps(event_inventory, **self.JSON_FORMAT)
                json_bytes = json_str.encode('utf-8')
                f.write(json_bytes)


    def set_scope(self, scope = "PRODUCTION"):
        if scope == 'PRODUCTION':
            self.scope = "PRODUCTION"
        else:
            raise NotImplementedError("Scope \"{0}\" not yet implemented".format(scope))


    # Properties
    @property
    def url_api(self):
        try:
            if self.scope == "PRODUCTION":
                return self.API_URL_PRODUCTION
            else:
                raise NotImplementedError("Scopes other than production not yet implemeted")
        except KeyError:
            raise ValueError("Error getting url_api - scope not yet set?")

    @property
    def url_login(self):
        return self.url_api + self.LOGIN_URL

    @property
    def url_inventory_search(self):
        return self.url_api + self.INVENTORY_SEARCH_V2_URL

    @property
    def url_event_information(self):
        return self.url_api + self.EVENT_INFORMATION_V2_URL

    @property
    def url_event_search(self):
        return self.url_api + self.EVENT_SEARCH_V3_URL

    @property
    def standard_headers(self):
        headers = {
            'Content-Type': self.CONTENT_TYPE,
            'Authorization': 'Bearer ' + self.access_token,
            'Accept': 'application/json',
            'Accept-Encoding': 'application/json',
        }
        return headers

# Exceptions
class GetListingsError(Exception):
    pass
class StubHub_API_Request_Error(Exception):
    pass

# Helpers
def warn(message, filename=None):
    """
    Print a warning to the screen and log in a file
    :param filename: Filename to append warning (or none))
    :return: None
    """
    print(message)
    if filename:
        with open(filename, 'a') as f:
            f.write(message + "\n")


if __name__ == "__main__":
    #
    # # # Test of getting and storing credentials
    # print("Number of StubHub_API_Request calls before test: ", StubHub_API_Request.i)
    # stubhub = StubHub_API()
    # stubhub.set_scope(scope='PRODUCTION')
    # loginfile = 'login_prod.json'
    # stubhub.set_login_info(loginfile=loginfile)
    # credfile = 'credentials_prod.json'
    # stubhub.store_credentials(file=credfile)
    # print("Number of StubHub_API_Request calls after test: ", StubHub_API_Request.i)

    # Test of getting everything from a listing
    # print("Number of StubHub_API_Request calls before test: ", StubHub_API_Request.i)
    # stubhub = StubHub_API()
    # stubhub.set_scope(scope='PRODUCTION')
    # credfile = 'credentials_prod.json'
    # stubhub.load_credentials(file=credfile)
    # eventid = "9873482" # Late August Panthers game vs Steelers
    # listfile = 'test_listing.json'
    # stubhub.store_event_inventory(filename=listfile, eventid=eventid)
    # print("Number of StubHub_API_Request calls after test: ", StubHub_API_Request.i)
    #
    # # Test of getting info for an event
    # print("Number of StubHub_API_Request calls before test: ", StubHub_API_Request.i)
    # stubhub = StubHub_API()
    # stubhub.set_scope(scope='PRODUCTION')
    # credfile = 'credentials_prod.json'
    # stubhub.load_credentials(file=credfile)
    # eventid = "9873482" # Late August Panthers game vs Steelers
    # event_info = stubhub.get_event_info(eventid=eventid)
    # pprint(event_info)
    # print("Number of StubHub_API_Request calls after test: ", StubHub_API_Request.i)

    # Test of getting info for an event
    print("Number of StubHub_API_Request calls before test: ", StubHub_API_Request.i)
    stubhub = StubHub_API()
    stubhub.set_scope(scope='PRODUCTION')
    credfile = 'credentials_prod.json'
    stubhub.load_credentials(file=credfile)
    stubhub.store_searched_events(filename="2017_Carolina_Panthers_events.json", query="\"at Carolina Panthers\" -Preseason -\"UNC Charlotte 49ers -\"Gameday Hospitality\"", city='Charlotte')
    # events = stubhub.search_events('Carolina Panthers', city='Charlotte')
    # pprint(events)
    # print(len(events['events']))
    print("Number of StubHub_API_Request calls after test: ", StubHub_API_Request.i)


