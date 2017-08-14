import base64
import requests
import json

# Globals
CONTENT_TYPE = 'application/x-www-form-urlencoded'
API_URL_PRODUCTION = 'https://api.stubhub.com/'
API_URL_SANDBOX = 'https://api.stubhubsandbox.com/'

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
    if scope == 'prod':
        scope = 'PRODUCTION'
        api_url = API_URL_PRODUCTION + "login"
    elif scope == 'dev':
        raise NotImplementedError("get_credentials not yet implemented for dev environment")
    else:
        raise ValueError("Invalid value for scope: " + scope )

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


# debug code
if __name__ == "__main__":

    # Test of getting and storing credentials
    loginfile = 'login_prod.json'
    store_credentials(loginfile, file='credentials_prod.json', scope='prod')