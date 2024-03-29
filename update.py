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

try:
    response = requests.get(API_URL)
    response.raise_for_status()
except requests.exceptions.HTTPError as err:
    sys.exit(f"::error::{err}")

# Account for the very rare possibility of a marketable app which doesn't appear in GetAppList
# To date, I only know of 1: The Vanishing of Ethan Carter VR (457880), a DLC which has it's own trading cards)
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

num_added = len(set(new_marketable_appids) - set(old_marketable_appids))
num_removed = len(set(old_marketable_appids) - set(new_marketable_appids))

if (num_removed > 10000):
    # Sometimes tens of thousands of apps will randomly disappear from ISteamApps/GetAppList
    # This rarely reflects an accurate state of the apps on Steam, and so these changes should be ignored
    # The number missing can range from 20,000 to 60,000 for a list that should contain 190,000 apps
    sys.exit(f"::warning::Unusually large number of apps removed ({num_removed}), ignoring changes")

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
