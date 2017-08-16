import base64
import requests
import json
from pprint import pprint

class StubHub_API(object):
    CONTENT_TYPE = 'application/x-www-form-urlencoded'
    API_URL_PRODUCTION = 'https://api.stubhub.com/'
    API_URL_SANDBOX = 'https://api.stubhubsandbox.com/'
    LOGIN_URL = 'login'
    INVENTORY_SEARCH_V2_URL = 'search/inventory/v2'
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

        print("Submitting request with token (unencoded): {0}".format(token_unencoded))
        print("Submitting request with token (encoded)  : {0}".format(token))

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

        # Should replace this with a class that actually knows how to properly handle these errors
        r = requests.post(self.url_login, headers=headers, data=data)
        if r.status_code != 200:
            raise Exception("API returned error code: {0}".format(r.status_code))

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

    def get_event_listings(self, eventid):
        """
        Get all listings from an event and return as a dict.

        :param eventid: Event ID for the event requested
        :return: Dict of event listings (including pricing and other summaries)
        """
        headers = {
            'Content-Type': self.CONTENT_TYPE,
            'Authorization': 'Bearer ' + self.access_token,
            'Accept': 'application/json',
            'Accept-Encoding': 'application/json',
        }
        params = {
            'eventid': eventid,
            'rows': 250,
            'start': 0,
            'zonestats': 'true',
            'sectionstats': 'true',
            'pricingsummary': 'true',
        }

        def make_request(url, headers, params):
            # TODO: Need to handle test for timeout, as I wont know how many recent requests have occurred.
            # TODO: Should this be a class that knows how to handle that sort of thing?
            # TODO: Make a API request class, that then has many routines or subclasses to do this stuff and has common error
            # TODO: handling?
            inv_request = requests.get(url, headers=headers, params=params)
            if inv_request.status_code != 200:
                raise Exception("API returned error code: {0}".format(inv_request.status_code))
            else:
                return inv_request.json()

        # Perform first inventory get
        i_max = 30
        i = 1
        inv = make_request(self.url_inventory_search, headers, params)
        print("get {2}: retrieved {0}/{1} listings".format(len(inv['listing']), inv['totalListings'], 1))
        # Loop through until you have all listings, appending the listing key of the return to the original inv
        # (all other returns, except for start, will be the same)
        while i < i_max and len(inv['listing']) < inv['totalListings']:
            i += 1
            params['start'] = len(inv['listing'])
            this_inv = make_request(self.url_inventory_search, headers, params)
            inv['listing'] = inv['listing'] + this_inv['listing']
            print("get {2}: retrieved {0}/{1} listings".format(len(inv['listing']), inv['totalListings'], i))

        # Right now I'm only returning inv rather than storing in this class.  Does that make sense?
        # This class is more for interacting with the StubHub API, and not about formatting the data I get from it.
        return inv


    def store_event_listings(self, filename = None, eventid = None):
        """
        Store all listings from an event to a file in JSON

        :param filename: File to store data to
        :param eventid: Event ID for the event requested
        :return: Dict of event listings (including pricing and other summaries)
        """
        event_listintgs = self.get_event_listings(eventid=eventid)
        with open(filename, 'w') as f:
            json.dump(event_listintgs, f, **self.JSON_FORMAT)


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



if __name__ == "__main__":

    # # Test of getting and storing credentials
    stubhub = StubHub_API()
    stubhub.set_scope(scope='PRODUCTION')
    loginfile = 'login_prod.json'
    stubhub.set_login_info(loginfile=loginfile)
    credfile = 'credentials_prod.json'
    stubhub.store_credentials(file=credfile)

    # Test of getting everything from a listing
    stubhub = StubHub_API()
    stubhub.set_scope(scope='PRODUCTION')
    credfile = 'credentials_prod.json'
    stubhub.load_credentials(file=credfile)
    eventid = "9873482" # Late August Panthers game vs Steelers
    listfile = 'test_listing.json'
    stubhub.store_event_listings(filename=listfile, eventid=eventid)