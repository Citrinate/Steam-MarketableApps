import json
import os.path
from pathlib import Path
import requests
import sys

# This script basically just caches the results of ISteamApps/GetAppList
# It also accounts for certain issues I've encountered when trying to use this API directly

API_URL = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
OUTPUT_FILE = Path(__file__).parent / "./data/marketable_apps.json"
OUTPUT_FILE_MIN = Path(__file__).parent / "./data/marketable_apps.min.json"
MARKETABLE_OVERRIDE_FILE = Path(__file__).parent / "./overrides/marketable_app_overrides.json"
UNMARKETABLE_OVERRIDE_FILE = Path(__file__).parent / "./overrides/unmarketable_app_overrides.json"
REMOVED_APPS_HISTORY = Path(__file__).parent / "./data/removed_apps_history.json" # Records the number of runs it's been since we last saw a removed app

try:
    response = requests.get(API_URL)
    response.raise_for_status()
except requests.exceptions.HTTPError as err:
    sys.exit(f"::error::{err}")

# Account for the very rare possibility of a marketable app which doesn't appear in GetAppList
# None currently exist, but historically I only know of 1: The Vanishing of Ethan Carter VR (457880), a DLC which has it's own trading cards (this game's cards became unmarketable on May 31, 2024 when the DLC was removed from sale on Steam)
marketable_overrides = list()
if os.path.exists(MARKETABLE_OVERRIDE_FILE):
    with open(MARKETABLE_OVERRIDE_FILE, "r") as infile:
        marketable_overrides = json.load(infile)

# Account for the even rarer possibility of an unmarketable app which does appears in GetAppList
# None exist to my knowledge, but maybe this will happen in the future
unmarketable_overrides = list()
if os.path.exists(UNMARKETABLE_OVERRIDE_FILE):
    with open(UNMARKETABLE_OVERRIDE_FILE, "r") as infile:
        unmarketable_overrides = json.load(infile)

try:
    new_marketable_appids = set(map(lambda x: x["appid"], response.json()["applist"]["apps"]))
    new_marketable_appids |= set(marketable_overrides)
    new_marketable_appids -= set(unmarketable_overrides)
    new_marketable_appids = list(new_marketable_appids)
    new_marketable_appids.sort()
except KeyError as e:
    sys.exit(f"::error::JSON key {e} not found")
except json.JSONDecodeError:
    sys.exit(f"::error::Invalid JSON returned from {API_URL}")

old_marketable_appids = list()
if os.path.exists(OUTPUT_FILE):
    with open(OUTPUT_FILE, "r") as infile:
        old_marketable_appids = json.load(infile)

removed = set(old_marketable_appids) - set(new_marketable_appids)
num_removed = len(removed)
num_added = len(set(new_marketable_appids) - set(old_marketable_appids))

# Sometimes apps will randomly disappear from ISteamApps/GetAppList only to re-appear an hour or so later
# The amount of apps this may effect can be as low as ~30 and as high as ~60,000 for a list that should contain ~190,000 apps
# To compensate, only consider an app removed if it hasn't appeared for 4 consecutive runs (which translates to 4 hours as this script is ran hourly)
# Example:
# https://github.com/Citrinate/Steam-MarketableApps/commit/12c81566389f81ad69a1fca865ad66bfe5193ad4 Added 36 apps, removed 38 apps (4 of the removed were marketable: 1196470,1266700,1310410,1282150)
# https://github.com/Citrinate/Steam-MarketableApps/commit/1af7a94b40f32d177699243034cabda636fd84a7 Added 56 apps, removed 6 apps (1 hour later, added back most of the 38 that were removed an hour earlier)
if (num_removed > 0):
    with open(REMOVED_APPS_HISTORY, "r+") as historyfile:
        removed_history = json.load(historyfile)
        for appid in removed_history.copy():
            if int(appid) not in removed:
                removed_history.pop(appid)

        for appid in removed.copy():
            remove = False
            if str(appid) not in removed_history:
                removed_history[str(appid)] = 1
            elif removed_history[str(appid)] >= 3:
                remove = True
            else:
                removed_history[str(appid)] += 1
            
            if remove == False:
                removed.remove(appid)
                new_marketable_appids.append(appid)
            else:
                removed_history.pop(str(appid))

        historyfile.seek(0)
        json.dump(removed_history, historyfile, indent = 4)
        historyfile.truncate()

    if (num_removed != len(removed)):
        num_removed_ignored = num_removed - len(removed)
        num_removed = len(removed)
        new_marketable_appids.sort()
        print(f"::notice::Ignoring the removal of {num_removed_ignored} apps")

if (num_added == 0 and num_removed == 0):
    print("::notice::No changes detected")
    sys.exit(0)

with open(OUTPUT_FILE, "w") as outfile, open(OUTPUT_FILE_MIN, "w") as outfile_min:
    json.dump(new_marketable_appids, outfile_min)
    json.dump(new_marketable_appids, outfile, indent = 4)

# https://github.com/orgs/community/discussions/28146#discussioncomment-4110404
commit_message = f'Added {num_added} apps, removed {num_removed} apps'
print(f"::notice::{commit_message}")
if "GITHUB_OUTPUT" in os.environ:
    with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
        print(f'COMMIT_MESSAGE={commit_message}', file=fh)

sys.exit(0)
