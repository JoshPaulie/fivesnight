"""
Dead simple bot used to organize LoL 5v5s

>> Run this file to start bot

Current features:
- Start "virtual queue" that splits players into 2 teams and assigns them roles
- The ability log which team won the previously made virtual queue
- Winrate leaderboard

Notes for those learning discord.py:
- This bot doesn't utilize cogs. There's not enough commands to warrant the use of them
- The ".sync" command is a newer standard and required to support modern "slash" commands
- Like many of my other bots, fivesnight is meant to used in a particular server
- Most edge cases are covered, minimizing the chance of a user getting "Interaction failed" message
"""
import os
import random
from dataclasses import dataclass
from typing import Any, TypeAlias

import discord
from discord.ext import commands

import match_history_management as match_manager

# Constants
MAIN_SERVER = discord.Object(id=1163270649540788254)
DEBUG_CHANNEL = discord.Object(id=1163272210807541880, type=discord.TextChannel)
FIVESNIGHT_TOKEN_ENVVAR_STR = "FIVESNIGHT_TOKEN"

# Custom Types
DiscordUser: TypeAlias = discord.Member | discord.User


@dataclass
class AssignedPlayer:
    player: DiscordUser
    role: str


# Helpers
def assign_roles(team: list[DiscordUser]) -> list[AssignedPlayer]:
    """'Assigns' a team roles by shuffling their order, then grabbing the next role (from top to bottom).
    Any leftover team members are given the 'Fill' role.
    This allows for more than 10 people to queue up, and let the bot randomly pick who gets to play
    """
    random.shuffle(team)
    roles = "Support Bottom Middle Jungle Top".split()
    assigned_roles = []
    for player in team:
        if roles:
            selected_role = roles.pop()
            assigned_roles.append(AssignedPlayer(player, selected_role))
            continue
        # If no more roles, give the extras "fill"
        assigned_roles.append(AssignedPlayer(player, "Fill"))
    return assigned_roles


def create_bullet_points(lst: list[Any]):
    """Takes list of items, return bullet point versions"""
    return [f"- {item}\n" for item in lst]


def list_to_multiline_string(lst: list[str]) -> str:
    """Helper for writing multiline embed descriptions, field values, etc, easier to hardcode"""
    result = ""
    for line in lst:
        result += f"{line}\n"
    return result


def calc_winrate(wins: int, games: int) -> str:
    """Returns user winrate in percentage form (with symbol)

    Example
        calc_winrate(2, 4) -> 50.0%
    """
    ratio = wins / games
    ratio_percentage = ratio * 100
    return f"{round(ratio_percentage, 1)}%"


# The bot class itself
class FivesnightBot(commands.Bot):
    team_one: list[DiscordUser] = []
    team_two: list[DiscordUser] = []

    def __init__(self, intents: discord.Intents, **kwargs):
        super().__init__(
            command_prefix=commands.when_mentioned_or("."),
            help_commands=False,
            intents=intents,
            **kwargs,
        )
        self.owner_id = 177131156028784640  # bexli boy

    async def setup_hook(self):
        self.tree.copy_global_to(guild=MAIN_SERVER)

    async def on_ready(self):
        assert self.user
        print(f"Logged on as {self.user} (ID: {self.user.id})")


# The actual bot instance
# Notes:
# Intents are basically permissions.
# The discord.Intents.all() generator gives the bot possible functionality, like seeing user's profiles and reading messages
# If your bot is designed for many servers, it's best to narrow down the intents
bot = FivesnightBot(intents=discord.Intents.all())


# Sync command
@bot.command(name="sync", description="[Meta] Syncs commands to server")
async def sync(ctx: commands.Context):
    if not await bot.is_owner(ctx.author):
        await ctx.reply("Only jarsh needs to use this 😬", ephemeral=True)
        return
    await bot.tree.sync(guild=MAIN_SERVER)
    assert ctx.guild
    await ctx.reply(f"Bot commands synced to {ctx.guild.name}")


# Clean up view for select messages
class DeleteThisMessageView(discord.ui.View):
    def __init__(self, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)

    @discord.ui.button(label="Delete this message", style=discord.ButtonStyle.danger)
    async def delete_me(self, interaction: discord.Interaction, button: discord.ui.Button):
        assert interaction.message
        await interaction.message.delete()


# Team creation
class TeamCreationView(discord.ui.View):
    def __init__(self, *, timeout: float | None = 180, organizer: DiscordUser):
        super().__init__(timeout=timeout)
        self.timeout_amount = timeout
        self.organizer = organizer
        self.queue: list[DiscordUser] = []
        self.team_one: list[DiscordUser] = []
        self.team_two: list[DiscordUser] = []

    # Join queue
    @discord.ui.button(label="Join", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        # Check: User is already in queue, nothing to do
        if user in self.queue:
            await interaction.response.defer()
            return
        self.queue.append(user)
        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"You've joined the queue!",
                description=f"Current queue size: ({len(self.queue)})",
                color=discord.Color.green(),
            ),
            ephemeral=True,
        )

    # Leave queue
    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        # Check: User isn't in queue, nothing to do
        if user not in self.queue:
            await interaction.response.defer()
            return
        self.queue.remove(user)
        await interaction.response.send_message(
            embed=discord.Embed(title="You've left the queue.", color=discord.Color.red()),
            ephemeral=True,
        )

    # Create teams
    @discord.ui.button(label="Create Teams", style=discord.ButtonStyle.blurple)
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check: Only organizer can start
        if not interaction.user == self.organizer:
            await interaction.response.send_message(
                f"Only the organizer ({self.organizer.name}) can finish the queue", ephemeral=True
            )
            return
        # Shuffle the queue order 3 times
        for _ in range(3):
            random.shuffle(self.queue)
        # Split queue in half, cram into teams
        self.team_one = self.queue[len(self.queue) // 2 :]
        self.team_two = self.queue[: len(self.queue) // 2]
        # Put the two teams into the bots memory for recording match outcomes later
        bot.team_one = self.team_one
        bot.team_two = self.team_two
        # End the view
        self.stop()

    @discord.ui.button(label="Check Queue", style=discord.ButtonStyle.gray, row=1)
    async def show_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue_len = len(self.queue)
        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"There {'are' if queue_len != 1 else 'is'} ({queue_len}) {'people' if queue_len != 1 else 'person'} in the queue",
                description="\n".join(create_bullet_points(self.queue)),
                color=discord.Color.greyple(),
            ),
            ephemeral=True,
        )


@bot.tree.command(
    name="create",
    description="Create a virtual queue for players to join (creates teams & assigns roles)",
)
async def create(interaction: discord.Interaction):
    # create team creation object (department of redundancy department)
    team_creator = TeamCreationView(organizer=interaction.user)
    # Send it with a cutie embed
    await interaction.response.send_message(
        embed=discord.Embed(
            title="A 5v5 is starting!",
            description=f"Organized by **{team_creator.organizer.name}**",
            color=discord.Color.blurple(),
        ),
        view=team_creator,
    )
    # Wait for view to finish (it's stopped by the organizer)
    await team_creator.wait()
    # Grab the two teams from the creator
    team_one = assign_roles(team_creator.team_one)
    team_two = assign_roles(team_creator.team_two)
    # Bypass team minimum check if in debug debug channel
    if interaction.channel != DEBUG_CHANNEL:
        # check: if either team is empty, stop the show (and shame them)
        if any([not len(team_one), not len(team_two)]):
            await interaction.followup.send(
                embed=discord.Embed(
                    title="bruh.. no friends?",
                    description="lol? 🤣",
                    color=discord.Color.dark_red(),
                ),
                ephemeral=True,
            )
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="This queue was discarded.",
                    description="One or more teams had 0 members.",
                    color=discord.Color.greyple(),
                ),
                view=DeleteThisMessageView(),
            )
            return
    # "Clean up" old message so people can't click the buttons
    await interaction.edit_original_response(
        embed=discord.Embed(title="This queue has ended.", color=discord.Color.greyple()), view=None
    )
    # Construct team embeds
    team_one_embed = discord.Embed(title="Team 1", color=discord.Color.blue())
    for member in team_one:
        team_one_embed.add_field(name=member.player, value=member.role)
    team_two_embed = discord.Embed(title="Team 2", color=discord.Color.red())
    for member in team_two:
        team_two_embed.add_field(name=member.player, value=member.role)
    # Send it!
    await interaction.followup.send(embeds=[team_one_embed, team_two_embed])
    await interaction.followup.send(
        embed=discord.Embed(
            title="Don't forget to record which team won 🏆",
            description="After the game, use the `/record` command to log the outcome of the match!",
            color=discord.Color.blurple(),
        ).set_footer(text="Your 5v5 winrate can be checked with /winrate"),
        view=DeleteThisMessageView(),
    )


# Record last game played
class RecordLastMatchView(discord.ui.View):
    def __init__(self, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.winning_team = []

    @staticmethod
    def record_team_one(winning_team: bool):
        """Update JSON file"""
        match_manager.add_player_match([player.id for player in bot.team_one], won_game=winning_team)

    @staticmethod
    def record_team_two(winning_team: bool):
        """Update JSON file"""
        match_manager.add_player_match([player.id for player in bot.team_two], won_game=winning_team)

    # Team One won
    @discord.ui.button(label="Team One", style=discord.ButtonStyle.blurple)
    async def team_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.record_team_one(winning_team=True)
        self.record_team_two(winning_team=False)
        self.winning_team = bot.team_one
        self.stop()

    # Team One won
    @discord.ui.button(label="Team Two", style=discord.ButtonStyle.red)
    async def team_two(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.record_team_one(winning_team=False)
        self.record_team_two(winning_team=True)
        self.winning_team = bot.team_two
        self.stop()


@bot.tree.command(name="record", description="Record the last match & indicate who won")
async def record(interaction: discord.Interaction):
    # check for recent match played
    if all([not bot.team_one, not bot.team_two]):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="There hasn't been a match played recently.",
                color=discord.Color.greyple(),
            ).set_footer(text="If there was a mistake recording a recent match, message jarsh"),
            view=DeleteThisMessageView(),
        )
        return
    record_match_view = RecordLastMatchView()
    await interaction.response.send_message(
        embed=discord.Embed(title="Who won the last game?", color=discord.Color.greyple()),
        view=record_match_view,
    )
    # Wait for someone to say who won
    await record_match_view.wait()
    # Edit org message so people can't double record the match
    random_emoji = random.choice(["😎", "💪", "🥳", "🏆"])
    await interaction.edit_original_response(
        embed=discord.Embed(
            title="Match recorded! GG!",
            description=f"Congrats to {', '.join(m.name for m in record_match_view.winning_team)} {random_emoji}",
            color=discord.Color.green(),
        ),
        view=None,
    )
    # Reset the bot's in-memory teams
    bot.team_one = []
    bot.team_two = []


# Winrate "leaderboard"
@bot.tree.command(name="winrates", description="Get everyone's winrates!")
async def winrates(interaction: discord.Interaction):
    # Create embed
    winrates_embed = discord.Embed(title="Match history!", color=discord.Color.blurple())
    for record in match_manager.get_match_history().items():
        user_id, match_history = record
        games_played = match_history[match_manager.GAMES_PLAYED_KEY]
        games_won = match_history[match_manager.GAMES_WON_KEY]
        assert interaction.guild
        winrates_embed.add_field(
            name=interaction.guild.get_member(user_id),
            value=f"{games_won}/{games_played} ({calc_winrate(games_won, games_played)})",
        )
    # Check: no winrates to display
    if not len(winrates_embed.fields):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="No games have been played yet.",
                color=discord.Color.greyple(),
            )
            ),
            view=DeleteThisMessageView(),
        )
        return
    # Send winrates embed
    await interaction.response.send_message(embed=winrates_embed, view=DeleteThisMessageView())


def main():
    if token := os.environ.get(FIVESNIGHT_TOKEN_ENVVAR_STR):
        bot.run(token)
        return
    print(f"No discord bot token for set in the environment variable: {FIVESNIGHT_TOKEN_ENVVAR_STR}")


if __name__ == "__main__":
    main()
