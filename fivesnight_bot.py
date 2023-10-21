#!/usr/bin/env python3


import os
import random
from dataclasses import dataclass
from typing import Any, TypeAlias

import discord
from discord.ext import commands

import match_history_management as match_manager

# Constants
MAIN_SERVER = discord.Object(id=1163270649540788254)
FIVESNIGHT_TOKEN_ENVVAR_STR = "FIVESNIGHT_TOKEN"

# Custom Types
DiscordUser: TypeAlias = discord.Member | discord.User


@dataclass
class AssignedPlayer:
    player: DiscordUser
    role: str


# Helpers
def assign_roles(team: list[DiscordUser]) -> list[AssignedPlayer]:
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
    result = ""
    for line in lst:
        result += f"{line}\n"
    return result


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
        print(f"Logged on as {self.user} (ID: {self.user.id})")  # type: ignore (this type ignore makes me want to kill conrad)


# Give the bot permissions so we can use it
intents = discord.Intents.default()
intents.message_content = True
bot = FivesnightBot(intents=intents)


# Sync command
@bot.command(name="sync", description="[Meta] Syncs commands to server")
async def sync(ctx: commands.Context):
    if not await bot.is_owner(ctx.author):
        await ctx.send("Only jarsh needs to use this 😬", ephemeral=True)
        await ctx.message.delete()
        return
    await bot.tree.sync(guild=MAIN_SERVER)
    await ctx.send("Synced.")


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
                title=f"You've joined the queue with {len(self.queue)} other(s).",
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
        # Put the two teams into the bots memory for recording later
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


# Team creation
@bot.tree.command(name="teams", description="Quickly create two even(ish) teams")
async def teams(interaction: discord.Interaction):
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
            view=None,
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


class RecordLastMatchView(discord.ui.View):
    def __init__(self, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)

    @staticmethod
    def record_team_one(winning_team: bool):
        for player in bot.team_one:
            match_manager.add_player_match(player.id, won_game=winning_team)

    @staticmethod
    def record_team_two(winning_team: bool):
        for player in bot.team_two:
            match_manager.add_player_match(player.id, won_game=winning_team)

    # Team One won
    @discord.ui.button(label="Team One", style=discord.ButtonStyle.blurple)
    async def team_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.record_team_one(winning_team=True)
        self.record_team_two(winning_team=False)
        self.stop()

    # Team One won
    @discord.ui.button(label="Team Two", style=discord.ButtonStyle.red)
    async def team_two(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.record_team_one(winning_team=False)
        self.record_team_two(winning_team=True)
        self.stop()


@bot.tree.command(name="record", description="Create the last match & indicate who won")
async def record(interaction: discord.Interaction):
    # check for recent match played
    if all([not bot.team_one, not bot.team_two]):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="There hasn't been a match played recently.", color=discord.Color.greyple()
            ),
        )
        return
    record_last_match_view = RecordLastMatchView()
    await interaction.response.send_message(
        embed=discord.Embed(title="Who won the last game?", color=discord.Color.greyple()),
        view=record_last_match_view,
    )
    # Wait for someone to say who won
    await record_last_match_view.wait()
    # Edit org message so people can't double record the match
    await interaction.edit_original_response(
        embed=discord.Embed(title="Match recorded! GG!", color=discord.Color.green()),
        view=None,
    )
    bot.team_one = []
    bot.team_two = []


def main():
    if token := os.environ.get(FIVESNIGHT_TOKEN_ENVVAR_STR):
        bot.run(token)
        return
    print(f"No discord bot token for set in the environment variable: {FIVESNIGHT_TOKEN_ENVVAR_STR}")


if __name__ == "__main__":
    main()
