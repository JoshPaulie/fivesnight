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
    "Discord IDs are ints, but json is literally the worst and only takes string keys"
    raw_match_history = get_match_history_raw()
    return {
        int(discord_user_id): player_match_history
        for discord_user_id, player_match_history in raw_match_history.items()
    }


def get_player_match_history(user_id: int) -> PlayerMatchHistory | None:
    """Get points for a certain user"""
    user_id_str = str(user_id)
    with open(MATCH_HISTORY_FILE_PATH, mode="r") as points_file:
        match_history: MatchHistory = json.load(points_file)
    return match_history.get(user_id_str)


def add_player_match(user_id: int, won_game: bool) -> None:
    """Update a user's match history"""
    user_id_str = str(user_id)
    # Read in
    with open(MATCH_HISTORY_FILE_PATH, mode="r") as points_file:
        match_history: MatchHistory = json.load(points_file)
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
