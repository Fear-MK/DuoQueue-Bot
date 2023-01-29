import asyncio
from datetime import datetime, timedelta
import random
from typing import List

from discord import ApplicationContext
from main import Channel
from utils import is_moderator, fetch_user_objs, get_teams_string, get_lineup_str


class Event:
    def __init__(self, channel: Channel):
        self.teams_str: str = ""
        self.active = False
        self.full = False
        self.team_size = 2
        self.teams_per_room = 6

        self.queue: List[str | List[str]] = []
        self.queue_flat: List[str] = []
        self.queue_num = 0
        self.unconfirmed_squads = []
        self.unconfirmed_flattened = []

        self.waiting_for_response = []

        self.teams = []

        self.channel = channel
        self.is_primary_leaderboard = True  # RT/CT
        self.leaderboard_type_str = None
        self.fill_time = None

    # NON-DISCORD FUNCTIONS

    def check_waiting(self, players):
        for d in self.unconfirmed_squads:
            if players[0] in d.keys() or players[-1] in d.keys():
                if players[0] in d.keys() and players[-1] in d.keys():
                    return d
                return False
        return None

    def check_list(self, players):
        for player in players:
            if player in self.queue_flat:
                return player
        return None

    async def remove_team_unconfirmed(self, name):
        squads = [list(d.keys()) for d in self.unconfirmed_squads]
        for i, array in enumerate(squads):
            if name in array:
                arr = array
                index = i
                break
        else:
            return
        del self.unconfirmed_squads[index]
        self.unconfirmed_flattened = [x for x in self.unconfirmed_flattened if x not in arr]

    async def update_queue_num(self, ctx, number):
        if self.queue_num + number == 12 and not self.queue_num > 12:
            self.queue_num += number
            self.full = True
            self.fill_time = datetime.now()
            await self.event_full(ctx)
        else:
            self.queue_num += number

    # DISCORD PROCESSES

    async def get_last_message_time(self, user):
        async for message in self.channel.history(limit=None, before=None, after=None, around=None):
            if message.author.display_name == user:
                message_time = message.created_at.replace(tzinfo=None)
                return message_time
        return None

    async def notify_and_remove(self, channel):
        if self.full:
            return

        current_time = datetime.now()
        inactive_users = []

        for user in self.queue_flat:
            if user in self.waiting_for_response:
                pass
            last_message_time = await self.get_last_message_time(user)

            if current_time - last_message_time >= timedelta(minutes=30):
                inactive_users.append(user)
                self.waiting_for_response.append(user)

                await channel.send(
                    f"{user}, please type something in the chat in the next 5 minutes to keep your spot in the mogi")

                await asyncio.sleep(300)

                last_message_time = await self.get_last_message_time(user)

                if current_time - last_message_time >= timedelta(seconds=5):
                    await self.remove(channel, self.queue_flat.index(user) + 1)

    async def event_full(self, ctx: ApplicationContext):
        solo_players = []
        team_players = []

        player_objs = fetch_user_objs(ctx, self.queue_flat[:12])
        await ctx.send(
            f"There are 12 players in the mogi.\nType `!l` to get a list of the current lineup.\n\n{', '.join([user.mention for user in player_objs])} Mogi has 12 players")

        for team in self.queue:
            if not isinstance(team, list):
                solo_players.append(team)
            else:
                team_players.append(team)

        random.shuffle(solo_players)

        solo_player_teams = [list(group) for group in zip(*[iter(solo_players)] * self.team_size)]

        completed_teams = solo_player_teams + team_players

        self.teams_str = get_teams_string(completed_teams)

        await ctx.send(f"{get_teams_string(completed_teams)}\n\nDecide a host amongst yourselves.")

    # DISCORD COMMANDS BEGIN

    async def start_mogi(self, ctx):
        if self.active == True:
            await ctx.send("You must end the current event before starting a new one.")
            return
        self.active = True
        await ctx.send(
            f"A new {str(self.team_size)}v{str(self.team_size)} mogi has started, type !c to join solo, or tag a partner to join as a team.")

    async def next(self, ctx):
        if not is_moderator(ctx):
            return

        await ctx.send("@here A mogi has started. Type `!c` if not currently playing")

    async def ping(self, ctx, number: int):

        if number == 0:
            number = 12 - len(self.queue_flat)

        if number > 6:
            return
        else:
            await ctx.message.delete()
            await ctx.send(f"@here +{number}")

    async def lineup(self, ctx: ApplicationContext, permanent: bool):
        lineup_str = get_lineup_str(self.queue)
        if permanent:
            await ctx.send(
                f"**Mogi List**\n\n{lineup_str}\nYou can use `!l` again in 30 seconds" if lineup_str != "" else "There are no players in the mogi.")
        else:
            msg = await ctx.send(
                f"**Mogi List**\n\n{lineup_str}\n" if lineup_str != "" else "There are no players in the mogi.")
            await msg.delete(delay=10)

    async def unconfirmed_lineup(self, ctx):
        output = "`Unconfirmed Squads`\n"
        if len(self.unconfirmed_flattened) == 0:
            await ctx.send("There are no unconfirmed squads.")
        for i, team in enumerate(self.unconfirmed_squads, start=1):
            line = f"`{str(i)}.`"
            for x in range(2):
                line += f" {list(team.keys())[x]}  `{'✓' if list(team.values())[x] == 'Confirmed' else '✘'} {list(team.values())[x]}`"
            output += line + "\n"
        await ctx.send(output)

    async def teams(self, ctx):
        if self.full == True:
            await ctx.send(self.teams_str)

    async def can(self, ctx: ApplicationContext, partners):
        if not self.active:
            await ctx.send("There is no mogi currently active in this channel, use !start to begin one.")
            return

        if self.queue_num >= 15:
            await ctx.send("Unable to join the mogi. The mogi currently has 15 players.")

        name = ctx.message.author.display_name
        partners.append(name)
        squad = partners

        if name in self.queue_flat:
            await ctx.send("You are already in the mogi. Please drop before trying to can again.")
            return

        if len(partners) < 2:
            checkList = self.check_list([name])
            if checkList == True:
                await ctx.send(f"{name} is already in the mogi. {str(self.queue_num)} players are in the mogi.")
                return

            elif name in self.unconfirmed_flattened:
                await ctx.send(
                    f"You are in an unconfirmed squad. Check the unconfirmed squads with `!ul` and type `!c @partner` to join the mogi with your squadmate, or `!d` to remove you and your team from the unconfirmed list.")
                return
            else:
                self.queue.append(name)
                self.queue_flat.append(name)
                await ctx.send(f"{name} has joined the mogi. {str(self.queue_num + 1)} players are in the mogi.")
                await self.update_queue_num(ctx, 1)
                return

        else:
            if partners[0] == partners[1]:
                await ctx.send("You can't make a squad with yourself.")
                return

            if self.queue_num == 11:
                await ctx.send("You cannot create/confirm a squad when there is only 1 slot in the mogi.")
                return

            if self.queue_num >= 12:
                await ctx.send("You cannot create/confirm a squad as a substitute")
                return

            checkList = self.check_list(squad)
            checkWaiting = self.check_waiting(squad)

            if checkList != None:
                await ctx.send(f"{checkList} is already in the mogi. They must drop before you can create a squad.")
                return

            if checkWaiting == False:
                await ctx.send(
                    "One of the players in your squad is in an unconfirmed squad, please drop before trying the command again.")
                return

            elif checkWaiting == None:  # Neither are queued
                self.unconfirmed_squads.append({squad[-1]: "Confirmed", squad[0]: "Unconfirmed"})
                self.unconfirmed_flattened.extend(squad)
                await ctx.send(
                    f"Created a squad with {squad[-1]} and {squad[0]}. {squad[0]} must type `!c @{squad[-1]}` to join the mogi.")
                return

            if isinstance(checkWaiting, dict):
                unconfirmed_squad = checkWaiting
                if unconfirmed_squad[name] == "Confirmed":
                    await ctx.send("You are already confirmed. Your partner must type `!c @Your Name`")
                    return
                else:
                    self.queue.append(squad)
                    self.queue_flat.extend(squad)

                    await ctx.send(
                        f"Squad confirmed: `{', '.join(squad)}`. {str(self.queue_num + 2)} players are in the mogi.")

                    await self.update_queue_num(ctx, 2)
                    await self.remove_team_unconfirmed(name)
                    return

    async def drop(self, ctx):
        if not self.active:
            await ctx.send("There is no mogi currently active in this channel, use !start to begin one.")
            return

        name = ctx.author.display_name

        if self.full and name in self.queue_flat[:12]:
            await ctx.send("You cannot drop from a mogi when it has filled.")
            return

        if name in self.unconfirmed_flattened:
            await self.remove_team_unconfirmed(name)
            await ctx.send("You have been removed from the unconfirmed squads.")
            return

        if name in self.queue_flat:
            for i, item in enumerate(self.queue):
                if isinstance(item, list):
                    if name in item:
                        team = item
                        user = fetch_user_objs(ctx, [item[1]] if item[0] == name else [item[0]])
                        await ctx.send(
                            f"{user[0].mention}, your teammate has dropped from the lineup, so you have been removed.")
                        del self.queue[i]
                        await self.update_queue_num(ctx, -2)
                        break
            else:
                team = [name]
                self.queue.remove(name)
                await self.update_queue_num(ctx, -1)
            self.queue_flat = [x for x in self.queue_flat if x not in team]
            await ctx.send(
                f"{name} and has dropped from the mogi. {str(self.queue_num)} players remaining in the mogi.")

        else:
            await ctx.send(
                f"{name} is already dropped from the mogi {str(self.queue_num)} players remaining in the mogi.")

    async def remove(self, channel: Channel, number: int) -> str:
        if not self.active:
            await channel.send("There is no mogi currently active in this channel, use `!start` to begin one.")
            return

        if number == None:  # If !r has no arguments
            await channel.send(f"{get_lineup_str(self.queue)}\nTo remove the 4th player on the list, use `!r 4`")

        number = int(number)

        if number > len(self.queue_flat) or number < 1:
            await channel.send("That number is not on the list. Use `!l` to see the players to remove")

        name = self.queue_flat[number - 1]
        for i, item in enumerate(self.queue):
            if isinstance(item, list):
                if name in item:
                    team = item
                    users = fetch_user_objs(channel, item)
                    del self.queue[i]
                    await self.update_queue_num(channel, -2)
                    break
        else:
            team = [name]
            users = fetch_user_objs(channel, [name])
            self.queue.remove(name)
            await self.update_queue_num(channel, -1)
        self.queue_flat = [x for x in self.queue_flat if x not in team]

        # note: this return value is only used in the command inside mogi.py
        return f"{', '.join([user.mention for user in users])} has been removed from the mogi. {str(len(self.queue_flat))} players remaining."
