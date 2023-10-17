#!/usr/bin/env python3


import os
import random
from collections import namedtuple
from typing import Any, TypeAlias

import discord
from discord.ext import commands

# Constants
MAIN_SERVER = discord.Object(id=1163270649540788254)
FIVESNIGHT_TOKEN_ENVVAR_STR = "FIVESNIGHT_TOKEN"

# Custom Types
AssignedPlayer = namedtuple("AssignedPlayer", "Player Role")
DiscordUser: TypeAlias = discord.Member | discord.User


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
            description=list_to_multiline_string(
                [
                    f"Organized by **{team_creator.organizer.name}**",
                ]
            ),
            color=discord.Color.blurple(),
        ),
        view=team_creator,
    )
    # Wait for view to finish (it's stopped by the organizer)
    await team_creator.wait()
    # "Clean up" old message so people can't click the buttons
    await interaction.edit_original_response(
        embed=discord.Embed(title="This queue has ended.", color=discord.Color.greyple()), view=None
    )
    # Grab the two teams from the creator
    team_one = assign_roles(team_creator.team_one)
    team_two = assign_roles(team_creator.team_two)
    # check: if either team is empty, stop the show (and shame them)
    if any([not len(team_one), not len(team_two)]):
        await interaction.followup.send(
            embed=discord.Embed(
                title="One of the teams had no members, no point in littering chat.",
                description="Also...no friends? lol? 🤣",
                color=discord.Color.dark_red(),
            ),
            ephemeral=True,
        )
        return
    # Construct team embeds
    team_one_embed = discord.Embed(title="Team 1", color=discord.Color.blue())
    for member in team_one:
        team_one_embed.add_field(name=member.Player, value=member.Role)
    team_two_embed = discord.Embed(title="Team 2", color=discord.Color.red())
    for member in team_two:
        team_two_embed.add_field(name=member.Player, value=member.Role)
    # Send it!
    await interaction.followup.send(embeds=[team_one_embed, team_two_embed])


def main():
    if token := os.environ.get(FIVESNIGHT_TOKEN_ENVVAR_STR):
        bot.run(token)
        return
    print(f"No discord bot token for set in the environment variable: {FIVESNIGHT_TOKEN_ENVVAR_STR}")


if __name__ == "__main__":
    main()
