import os
import copy
import datetime
from Event import Event, Panthers, Hornets, summarize_events

# Settings
team='Panthers'
e_dict = {'Panthers': Panthers,
          'Hornets': Hornets}
date = '2017-11-07'
data_dir = "./2017_{0}/".format(team)
start = None
stop = None
step = datetime.timedelta(days=-1)

# Main
print("Test {0} summarize events".format(team))
eventids = None
save_to = './2017_{1}_Processed_Data/{0}_Panthers_DataFrame.csv'.format(date, team)
ps_template = {
                'ylim': (-100, 300),
                'price_type': 'rel'}
plot_settings = []
stg = e_dict[team].get_season_ticket_groups()
for g in stg:
    ps_local = copy.deepcopy(ps_template)
    ps_local['prefix'] = "./2017_{2}_Processed_Data/Plots/{1}/{0}/".format(g, date, team)
    ps_local['groups'] = [g]
    plot_settings.append(ps_local)

# Make all required plot directories
for ps in plot_settings:
    if not os.path.isdir(ps['prefix']):
        os.makedirs(ps['prefix'])

df = summarize_events(e_dict[team], save_to=save_to, eventids=eventids, directory=data_dir, tp_slice=slice(start, stop, step),
                      plot_settings=plot_settings)