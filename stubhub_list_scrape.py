import json
import time
from StubHub_API import StubHub_API, StubHub_API_Request_Error, GetListingsError
import datetime

JSON_FORMAT = {'sort_keys': True, 'indent': 4, 'separators': (',', ': ')}
DATETIME_FORMAT = "%Y-%m-%d_%H-%M-%S"

def stubhub_list_scrape(credfile='credentials_prod.json', eventfile='events.json', settingsfile='settings.json', warnfile='warnings.log', handle_failures=True):
    """
    Continuously scrapes listings from a set of StubHub events and stores them to files.

    :param eventfile:
    :param settingsfile:
    :param warnfile: File to store some warnings (a hacky way to highlight these warnings separate from other messages)
    :param handle_failures: If True, handle StubHub_API_Request_Errors and continue logging for other events
    :return:
    """
    # Instance the StubHub_API and get credentials
    stubhub = StubHub_API()
    stubhub.set_scope(scope='PRODUCTION')
    stubhub.load_credentials(file=credfile)

    while True:
        print("Loading settings and next EventID")
        settings = load_settings(settingsfile)
        event = get_next_event(eventfile=eventfile, update_eventfile=True, remove_next=True, add_next_to_end=True)
        event_loc = event.get('save_location', './')
        eventid = event['eventid']
        file_format = event.get('file_format', 'txt')

        now = datetime.datetime.today().strftime(DATETIME_FORMAT)
        list_file = event_loc + '/' + str(eventid) + "_" + now + ".json"
        print("Saving listings for event {0} in file {1}".format(eventid, list_file))
        try:
            stubhub.store_event_inventory(filename=list_file, eventid=eventid, file_format=file_format, warnfile=warnfile)
        except (StubHub_API_Request_Error, GetListingsError) as e:
            if handle_failures:
                warn("{1}: Warning: Failed to store event inventory for event {0} - event skipped".format(eventid, now), filename=warnfile)
            else:
                raise e
        if settings['stop']:
            print("Stop requested in settings file - stopping scrape")
            break
        else:
            print("Sleeping {0} seconds before next action".format(settings['wait_between_listings']))
            time.sleep(settings['wait_between_listings'])

def load_settings(settingsfile=None):
    """
    Loads stubhub_list_scrape settings, applying defaults to any that are missing, and returns as a dict.

    :param settingsfile:
    :return: dict of settings
    """
    # Load settings
    with open(settingsfile, 'r') as f:
        settings = json.load(f)

    # Apply defaults
    settings['stop'] = settings.get('stop', False)
    settings['wait_between_listings'] = settings.get('wait_between_listings', 60)

    return settings


def get_next_event(eventfile=None, update_eventfile=True, remove_next=True, add_next_to_end=True):
    """
    Return the next event in an eventfile and then overwrite the eventfile with an updated set of events.

    :param eventfile:
    :param remove_next: If True, remove the first event in the list before saving the eventfile
    :param add_next_to_end: If True, add_seat the first event in the list to the end of the list before saving the eventfile
    :return: The eventid of the next event in the list
    """

    with open(eventfile, 'r') as f:
        events = json.load(f)['events']
    next_event = events[0]

    if update_eventfile:
        if remove_next:
            events.pop(0)

        if add_next_to_end:
            events.append(next_event)

        with open(eventfile, 'w') as f:
            json.dump({'events': events}, f, **JSON_FORMAT)

    return next_event

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
    stubhub_list_scrape(eventfile='events_Panthers_Hornets.json')