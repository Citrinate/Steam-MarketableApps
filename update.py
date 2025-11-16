import json
import os.path
from pathlib import Path
import requests
import sys

# https://steamapi.xpaw.me/#IStoreService/GetAppList
API_URL = (
    "https://api.steampowered.com/IStoreService/GetApplist/v1"
    "?max_results=50000"
    "&include_games=true"
    "&include_dlc=true"
    "&include_software=true"
    "&include_videos=true"
    "&include_hardware=true"
)

OUTPUT_FILE = Path(__file__).parent / "./data/marketable_apps.json"
OUTPUT_FILE_MIN = Path(__file__).parent / "./data/marketable_apps.min.json"
MARKETABLE_OVERRIDE_FILE = Path(__file__).parent / "./overrides/marketable_app_overrides.json"
UNMARKETABLE_OVERRIDE_FILE = Path(__file__).parent / "./overrides/unmarketable_app_overrides.json"

def load_json_if_exists(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default

# Get list of marketable appIDs from GetApplist
new_marketable_appids = set()
try:
    have_more_results = True
    last_appid = 0
    while have_more_results:
        response = requests.get(API_URL, params={"key": os.getenv("STEAM_API_KEY"), "last_appid": last_appid})
        response.raise_for_status()
        try:
            new_marketable_appids |= set(map(lambda x: x["appid"], response.json()["response"]["apps"]))
            have_more_results = response.json()["response"].get("have_more_results", False)
            last_appid = response.json()["response"].get("last_appid", 0)
        except KeyError as e:
            sys.exit(f"::error::JSON key {e} not found")
        except json.JSONDecodeError:
            sys.exit(f"::error::Invalid JSON returned from API at {last_appid}")
except requests.exceptions.HTTPError as err:
    sys.exit(f"::error::{err}")

# Add known marketable appIDs that are missing from GetAppList
new_marketable_appids |= set(load_json_if_exists(MARKETABLE_OVERRIDE_FILE, []))

# Remove known unmarketable appIDs that appear in GetAppList
new_marketable_appids -= set(load_json_if_exists(UNMARKETABLE_OVERRIDE_FILE, []))

# Save updated list
old_marketable_appids = set(load_json_if_exists(OUTPUT_FILE, []))
num_removed = len(old_marketable_appids - new_marketable_appids)
num_added = len(new_marketable_appids - old_marketable_appids)
commit_message = f'Added {num_added} apps, removed {num_removed} apps'

if (num_added == 0 and num_removed == 0):
    print("::notice::No changes detected")
else:
    print(f"::notice::{commit_message}")
    with open(OUTPUT_FILE, "w") as outfile, open(OUTPUT_FILE_MIN, "w") as outfile_min:
        new_marketable_appids = sorted(new_marketable_appids)
        json.dump(new_marketable_appids, outfile_min)
        json.dump(new_marketable_appids, outfile, indent = 4)

# https://github.com/orgs/community/discussions/28146#discussioncomment-4110404
if "GITHUB_OUTPUT" in os.environ:
    with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
        print(f'COMMIT_MESSAGE={commit_message}', file=fh)

sys.exit(0)
