import base64
import requests
import json
from pprint import pprint


# Globals
CONTENT_TYPE = 'application/x-www-form-urlencoded'
API_URL_PRODUCTION = 'https://api.stubhub.com/'
API_URL_SANDBOX = 'https://api.stubhubsandbox.com/'
LOGIN_URL = 'login'
INVENTORY_SEARCH_V2_URL = 'search/inventory/v2'

def get_credentials(loginfile=None, scope='prod'):
    """
    Given username, password, key, and secret, return access token and other data from StubHub login API.

    :param loginfile: (Optional) If string, denotes the name of a JSON formatted file with username, password, key, and
                      secret.
                      If dictionary, includes entries for username, password, key, and secret
                      If None, function will prompt user for username, password, key, and secret.
    :param scope:     The StubHub environment to login ("prod" or "dev")
    :return:          A dictionary including:
            "access_token":
            "expires_in":
            "refresh_token":
            "scope":
            "token_type":
    """
    scope, api_url = scope2props(scope)

    if loginfile is None:
        raise NotImplementedError("get_credentials not yet implemented for user-input login/password/key/secret")
    elif isinstance(loginfile, str):
        with open(loginfile, 'r') as f:
            loginfile = json.load(f)
    elif isinstance(loginfile, dict):
        # Interact with it the same as the json file below
        pass
    else:
        raise ValueError("Invalid value for loginfile: " + scope )
    c_key = loginfile['c_key']
    c_secret = loginfile['c_secret']
    username = loginfile['username']
    password = loginfile['password']

    # base64 takes 8-bit binary byte data, not a string object.  Use .encode to convert this.
    # https://stackoverflow.com/questions/8908287/base64-encoding-in-python-3
    token_unencoded = c_key + ":" + c_secret
    token = base64.b64encode(token_unencoded.encode('utf-8'))

    print("Submitting request with token (unencoded): {0}".format(token_unencoded))
    print("Submitting request with token (encoded)  : {0}".format(token))

    # Login Request via POST to API
    # Not 100% sure what this extra decode is needed for
    headers = {'Content-Type': CONTENT_TYPE,
               'Authorization': 'Basic ' + token.decode('utf-8')}
    data = {
        'grant_type': 'password',
        'username': username,
        'password': password,
        'scope': scope
    }

    r = requests.post(api_url, headers=headers, data=data)

    if r.status_code != 200:
        raise Exception("API returned error code: {0}".format(r.status_code))

    # Return full credential info in dictionary json format
    return r.json()


def store_credentials(loginfile=None, file="credentials_prod.json", scope='prod'):
    """
    Given username, password, key, and secret, save access token and other data from StubHub login API to a file.

    :param loginfile: See get_credentials()
    :param file:      Name of file to save credentials to in JSON format.
    :param scope:     See get_credentials()
    :return:          None
    """

    cred = get_credentials(loginfile=loginfile, scope=scope)
    with open(file, 'w') as f:
        json.dump(cred, f, sort_keys=True, indent=4, separators=(',', ': '))


def load_credentials(cred="credentials_prod.json"):
    """
    Load Stubhub login credentials from a JSON formatted file and return as a dict.

    :param cred: Either a string denoting a file with JSON formatted credentials, or a dictionary
                 to be validated as credentials
    :return: Validated dictionary of credentials including:
            "access_token":
            "expires_in":
            "refresh_token":
            "scope":
            "token_type":
    """
    if isinstance(cred, dict):
        # Easy way to handle if a function was handed valid credentials
        pass
    elif isinstance(cred, str):
        with open(cred, 'r') as f:
            cred = json.load(f)
    else:
        raise ValueError("Invalid input cred={0}".format(cred))

    # Check for correct entries
    cred_keys = [ "access_token", "expires_in", "refresh_token", "scope", "token_type"]
    for k in cred_keys:
        if k not in cred:
            raise ValueError("Credentials missing key {0}".format(k))
    return cred


def get_event_listings(eventid, credentials, scope='prod', start=0, rows=250):
    scope, api_url = scope2props(scope)
    url = api_url + INVENTORY_SEARCH_V2_URL
    cred = load_credentials(credentials)
    headers = inv_headers(cred['access_token'])
    params = {
        'eventid': eventid,
        'rows': rows,
        'start': start,
        'zonestats': 'true',
        'sectionstats': 'true',
        'pricingsummary': 'true',
    }

    def make_request(url, headers, params):
        #TODO: Need to handle test for timeout, as I wont know how many recent requests have occurred.
        #TODO: Should this be a class that knows how to handle that sort of thing?
        #TODO: Make a API request class, that then has many routines or subclasses to do this stuff and has common error
        #TODO: handling?
        inv_request = requests.get(url, headers=headers, params=params)
        if inv_request.status_code != 200:
            raise Exception("API returned error code: {0}".format(inv_request.status_code))
        else:
            return inv_request.json()

    # Perform first inventory get
    i_max = 30
    i = 1
    inv = make_request(url, headers, params)
    print("get {2}: retrieved {0}/{1} listings".format(len(inv['listing']), inv['totalListings'], 1))
    # Loop through until you have all listings, appending the listing key of the return to the original inv
    # (all other returns, except for start, will be the same)
    while i < i_max and len(inv['listing']) < inv['totalListings']:
        i += 1
        params['start'] = len(inv['listing'])
        this_inv = make_request(url, headers, params)
        inv['listing'] = inv['listing'] + this_inv['listing']
        print("get {2}: retrieved {0}/{1} listings".format(len(inv['listing']), inv['totalListings'], i))

    return inv


def store_event_listings(filename, **kwargs):
    event_listintgs = get_event_listings(**kwargs)
    with open(filename, 'w') as f:
        json.dump(event_listintgs, f, sort_keys=True, indent=4, separators=(',', ': '))


# Helpers
def scope2props(scope):
    if scope == 'prod':
        scope = 'PRODUCTION'
        api_url = API_URL_PRODUCTION
    elif scope == 'dev':
        raise NotImplementedError("get_credentials not yet implemented for dev environment")
    else:
        raise ValueError("Invalid value for scope: " + scope )
    return scope, api_url


def inv_headers(access_token):
    """
    Return the headers required for an Inventory Search API get request

    :param access_token:
    :return:
    """
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Bearer ' + access_token,
        'Accept': 'application/json',
        'Accept-Encoding': 'application/json',
    }
    return headers


# debug code
if __name__ == "__main__":

    # # Test of getting and storing credentials
    # loginfile = 'login_prod.json'
    # store_credentials(loginfile, file='credentials_prod.json', scope='prod')

    # Test of getting everything from a listing
    eventid = "9873482" # Late August Panthers game vs Steelers
    rows = 250 # Just something big to get everything
    credentials = 'credentials_prod.json' # get the credentials from a file
    filename = 'test_listing.json'
    # listings = get_event_listings(eventid, credentials, scope='prod', rows=rows)
    store_event_listings(filename, eventid=eventid, credentials=credentials, scope='prod', rows=rows)