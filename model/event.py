import asyncio
from datetime import datetime, timedelta
import random
from typing import List
from discord import ApplicationContext, Member
from model.types import Channel, SquadStatus, Squad, SquadPlayer
from utils import fetch_user_objs, get_teams_string, get_lineup_str


class Event:
    def __init__(self, server_id: int, channel: Channel):
        self.teams_str: str = ""
        self.active = False
        self.full = False
        self.team_size = 2
        self.teams_per_room = 6

        self.queue: List[Squad | str] = []
        self.queue_flat: List[str] = []
        self.queue_num = 0
        self.unconfirmed_squads: List[Squad] = []

        self.waiting_for_response = []

        self.teams = []

        self.channel = channel
        self.server_id = server_id
        self.is_primary_leaderboard = True  # RT/CT
        self.leaderboard_type_str = None
        self.fill_time = None

    # NON-DISCORD FUNCTIONS

    def check_waiting(self, players: List[str]) -> SquadStatus:
        # important convention: the caller is always players[-1]
        caller_name = players[-1]
        partner_name = players[0]

        for squad in self.unconfirmed_squads:
            has_caller = squad.has_player(caller_name)
            has_partner = squad.has_player(partner_name)
            if has_caller and not has_partner:
                return SquadStatus.CALLER_IN_OTHER_SQUAD
            if has_caller:
                caller = squad.get_player(caller_name)
                if caller.confirmed:
                    return SquadStatus.WAITING_ON_PARTNER
                else:
                    return SquadStatus.CONFIRMING

        return SquadStatus.NEITHER_UNCONFIRMED

    def check_list(self, players):
        for player in players:
            if player in self.queue_flat:
                return player
        return None

    async def remove_team_unconfirmed(self, name: str):
        updated_squads = [squad for squad in self.unconfirmed_squads if not squad.has_player(name)]
        self.unconfirmed_squads = updated_squads

    async def update_queue_num(self, number):
        if self.queue_num + number == 12 and not self.queue_num > 12:
            self.queue_num += number
            self.full = True
            self.fill_time = datetime.now()
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

            # could be None
            if not last_message_time:
                continue

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
            if isinstance(team, Squad):
                team_players.append([team.player_1.name, team.player_2.name])
            else:
                solo_players.append(team)

        random.shuffle(solo_players)

        solo_player_teams = [list(group) for group in zip(*[iter(solo_players)] * self.team_size)]

        completed_teams = solo_player_teams + team_players

        self.teams_str = get_teams_string(completed_teams)

        await ctx.send(f"{get_teams_string(completed_teams)}\n\nDecide a host amongst yourselves.")

    # DISCORD COMMANDS BEGIN

    async def start_mogi(self, ctx):
        if self.active:
            await ctx.send("You must end the current event before starting a new one.")
            return
        self.active = True
        await ctx.send(
            f"A new {str(self.team_size)}v{str(self.team_size)} mogi has started, type !c to join solo, or tag a partner to join as a team.")

    async def next(self, ctx):
        if self.active:
            await ctx.send("There is already an active mogi. Use `!esn` if you'd like to start a new one.")
            return

        # Not sure if I understand the purpose of this. It doesn't actually start a new mogi...
        await ctx.send("@here A mogi has started. Type `!c` if not currently playing")

    async def ping(self, ctx):

        number = 12 - len(self.queue_flat)

        if number > 6:
            return
        else:
            await ctx.message.delete()
            await ctx.send(f"@here +{number}")

    async def lineup(self, ctx: ApplicationContext, permanent: bool):
        lineup_str = get_lineup_str(self.queue)
        if not self.active:
            await ctx.send("There is no active mogi in this channel. Use `!s` to start one")
            return
        if permanent:
            await ctx.send(
                f"**Mogi List**\n\n{lineup_str}\nYou can use `!l` again in 30 seconds" if lineup_str != "" else "There are no players in the mogi.")
        else:
            msg = await ctx.send(
                f"**Mogi List**\n\n{lineup_str}\n" if lineup_str != "" else "There are no players in the mogi.")
            await msg.delete(delay=10)

    async def unconfirmed_lineup(self, ctx):
        output = "`Unconfirmed Squads`\n"
        if len(self.unconfirmed_squads) == 0:
            await ctx.send("There are no unconfirmed squads.")
            return
        for i, squad in enumerate(self.unconfirmed_squads):
            line = f"`{str(i + 1)}.`"
            # player 1
            line += f" {squad.player_1.name}  `{'✓ Confirmed' if squad.player_1.confirmed else '✘ Unconfirmed'}` / "
            # player 2
            line += f" {squad.player_2.name}  `{'✓ Confirmed' if squad.player_2.confirmed else '✘ Unconfirmed'}`"
            output += line + "\n"
        await ctx.send(output)

    async def post_teams(self, ctx):
        if self.full:
            await ctx.send(self.teams_str)
        await ctx.send("The mogi is not full yet.")

    async def can(self, ctx: ApplicationContext, squad_names: List[str]) -> int:
        if not self.active:
            await ctx.send("There is no mogi currently active in this channel, use !start to begin one.")
            return 0

        if self.queue_num >= 15:
            await ctx.send("Unable to join the mogi. The mogi currently has 15 players.")
            return 0

        name = ctx.message.author.display_name
        # add the caller to the squad
        squad_names.append(name)

        if name in self.queue_flat:
            # This implies that someone has to drop and !c while pinging someone else to duo
            await ctx.send("You are already in the mogi. Please drop before trying to can again.")
            return 0

        players_in_event: List[str] = [player for player in squad_names if player in self.queue_flat]
        # if only one person is queuing
        if len(squad_names) < 2:
            if len(players_in_event) > 0:
                await ctx.send(f"{name} is already in the mogi. {str(self.queue_num)} players are in the mogi.")
                return 0

            # if the person is in an unconfirmed duo
            elif len([squad for squad in self.unconfirmed_squads if squad.has_player(name)]) > 0:
                await ctx.send(
                    f"You are in an unconfirmed squad. Check the unconfirmed squads with `!ul` and type `!c @partner` to join the mogi with your squadmate, or `!d` to remove you and your team from the unconfirmed list.")
                return 0
            else:
                self.queue.append(name)
                self.queue_flat.append(name)
                await ctx.send(f"{name} has joined the mogi. {str(self.queue_num + 1)} players are in the mogi.")
                await self.update_queue_num(1)
                return 1

        # duo queue logic
        else:
            if squad_names[0] == squad_names[1]:
                await ctx.send("You can't make a squad with yourself.")
                return 0

            if self.queue_num == 11:
                await ctx.send("You cannot create/confirm a squad when there is only 1 slot in the mogi.")
                return 0

            if self.queue_num >= 12:
                await ctx.send("You cannot create/confirm a squad as a substitute")
                return 0

            if len(players_in_event) > 0:
                await ctx.send(
                    f"{players_in_event[0]} is already in the mogi. They must drop before you can create a squad.")
                return 0

            squad_status: SquadStatus = self.check_waiting(squad_names)

            if squad_status == SquadStatus.CALLER_IN_OTHER_SQUAD:
                await ctx.send(
                    "You are already in an unconfirmed squad, please drop before trying the command again.")
                return 0

            if squad_status == SquadStatus.NEITHER_UNCONFIRMED:  # Neither are queued
                player_1 = SquadPlayer(squad_names[-1], True)
                player_2 = SquadPlayer(squad_names[0], False)
                unconfirmed_squad = Squad(player_1, player_2)
                self.unconfirmed_squads.append(unconfirmed_squad)
                await ctx.send(
                    f"Created a squad with {player_1.name} and {player_2.name}. {player_2.name} must type `!c @{player_1.name}` to join the mogi.")
                return 0

            if squad_status == SquadStatus.WAITING_ON_PARTNER:
                await ctx.send("You are already confirmed. Your partner must type `!c @Your Name`")
                return 0

            if squad_status == SquadStatus.CONFIRMING:
                # this should always be safe
                confirmed_squad = [squad for squad in self.unconfirmed_squads if squad.has_player(name)][0]
                confirmed_squad.player_1.confirmed = True
                confirmed_squad.player_2.confirmed = True
                self.queue.append(confirmed_squad)
                self.queue_flat.extend(squad_names)

                await ctx.send(
                    f"Squad confirmed: `{', '.join(squad_names)}`. {str(self.queue_num + 2)} players are in the mogi.")

                await self.update_queue_num(2)
                await self.remove_team_unconfirmed(name)
                return 2

    async def find_and_remove_player(self, ctx: ApplicationContext, name: str) -> List[Member]:
        users = []
        for i, item in enumerate(self.queue):
            if isinstance(item, Squad):
                # if this squad has the player to delete, remove it
                if item.has_player(name):
                    # pop it from the queue
                    self.queue.pop(i)
                    # use a list comprehension to set queue_flat to all names that are not in that squad
                    self.queue_flat = [p_name for p_name in self.queue_flat if not item.has_player(p_name)]
                    users = fetch_user_objs(ctx, [item.player_1.name, item.player_2.name])
                    await self.update_queue_num(-2)
                    break
            elif item == name:
                team = [name]
                users = fetch_user_objs(ctx, [name])
                self.queue.remove(name)
                self.queue_flat = [x for x in self.queue_flat if x not in team]
                await self.update_queue_num(-1)
                break
        return users

    async def drop(self, ctx):
        if not self.active:
            await ctx.send("There is no mogi currently active in this channel, use !start to begin one.")
            return

        name = ctx.author.display_name

        if self.full and name in self.queue_flat[:12]:
            await ctx.send("You cannot drop from a mogi when it has filled.")
            return

        name_in_squad = len([squad for squad in self.unconfirmed_squads if squad.has_player(name)]) > 0
        if name_in_squad:
            await self.remove_team_unconfirmed(name)
            await ctx.send("You have been removed from the unconfirmed squads.")
            return

        users: List[Member] = await self.find_and_remove_player(ctx, name)
        if len(users) == 2:
            mention_str = users[1].mention if users[0].display_name == name else users[0].mention
            await ctx.send(
                f"{mention_str}, your teammate has dropped from the lineup, so you have been removed.")
        elif len(users) == 1:
            await ctx.send(
                f"{name} has dropped from the mogi. {str(self.queue_num)} players remaining in the mogi.")
        else:
            await ctx.send(
                f"{name} is not in the mogi")

    async def remove(self, ctx: ApplicationContext, number: int) -> str:
        # To avoid some annoying type errors, this returns a message to be sent in the command
        if not self.active:
            return "There is no mogi currently active in this channel, use `!start` to begin one."

        if number > len(self.queue_flat) or number < 1:
            return "That number is not on the list. Use `!l` to see the players to remove"

        name = self.queue_flat[number - 1]
        users = await self.find_and_remove_player(ctx, name)

        # note: this return value is only used in the command inside mogi.py
        return f"{', '.join([user.mention for user in users])} has been removed from the mogi. {str(len(self.queue_flat))} players remaining."
