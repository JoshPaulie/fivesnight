"""
Crude match history system, tracked in a json file

>> Run this file in interactive mode to manage the match history file

Notes:
- json is bad and only has strings for keys
- Each discord.User has an id property, a reliable way to retrieve a discord user's data (ie. Display name)
- This id is (predictably) an int
- Most of these functions take ints as arguments but simply convert them to strings to do the actual json getting/setting

Example file:
{"0000000000": {"games": 0, "won": 0}}
"""
import json
import pathlib
import sys

MATCH_HISTORY_FILE_PATH = "match_history.json"
GAMES_PLAYED_KEY = "games"
GAMES_WON_KEY = "wins"

PlayerMatchHistory = dict[str, int]
MatchHistory = dict[str, PlayerMatchHistory]


def points_file_exists() -> bool:
    # This straight up just doesn't work
    return pathlib.Path(MATCH_HISTORY_FILE_PATH).exists()


def create_match_history_file() -> None:
    """Create new JSON file, or reset it.

    Meant to be used in interactive mode to generate the file"""
    if points_file_exists:
        if input("File already exists. Would you like to overwrite it (y or n): ").lower() not in ["y", "n"]:
            return
    with open(MATCH_HISTORY_FILE_PATH, mode="w") as points_file:
        json.dump({}, points_file)


def get_match_history_raw() -> MatchHistory:
    """The JSON -> dict translation (but with strings for keys)"""
    with open(MATCH_HISTORY_FILE_PATH, mode="r") as points_file:
        match_history: MatchHistory = json.load(points_file)
    return match_history


def get_match_history() -> dict[int, PlayerMatchHistory]:
    """Returns the match history but discord IDs are usable ints

    (this is necessary bc json is only takes string keys, and discord wants the ids as ints)
    """
    return {
        int(discord_user_id): player_match_history
        for discord_user_id, player_match_history in get_match_history_raw().items()
    }


def get_player_match_history(user_id: int) -> PlayerMatchHistory | None:
    """Get the match history of a particular player"""
    user_id_str = str(user_id)
    with open(MATCH_HISTORY_FILE_PATH, mode="r") as points_file:
        match_history: MatchHistory = json.load(points_file)
    return match_history.get(user_id_str)


def add_player_match(user_ids: int | list[int], won_game: bool) -> None:
    """Update user(s) match history"""
    # Allows the func to still take only 1 user id, if need be
    if isinstance(user_ids, int):
        user_ids = [user_ids]

    # Read in
    with open(MATCH_HISTORY_FILE_PATH, mode="r") as points_file:
        match_history: MatchHistory = json.load(points_file)

    for user_id in user_ids:
        user_id_str = str(user_id)
        # Make sure user has a record
        if user_id_str not in match_history.keys():
            match_history.update({user_id_str: {GAMES_PLAYED_KEY: 0, GAMES_WON_KEY: 0}})
        # Make match history changes
        match_history[user_id_str][GAMES_PLAYED_KEY] += 1
        if won_game:
            match_history[user_id_str][GAMES_WON_KEY] += 1

    # Write out
    with open(MATCH_HISTORY_FILE_PATH, mode="w") as points_file:
        json.dump(match_history, points_file)


def main():
    if not sys.flags.interactive:
        print("This script is meant to be ran in interactive mode, or imported.")
        return


if __name__ == "__main__":
    main()
