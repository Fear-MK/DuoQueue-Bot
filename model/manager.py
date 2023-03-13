from datetime import datetime, timedelta
from typing import List, Dict
from discord import Bot, Message, ApplicationContext
from model.event import Event
from model.serversettings import ServerSettings
from time import time as current_unix_epoch_timestamp
from test.testevent import TestEvent
from utils import is_moderator


class Manager:

    def __init__(self, bot: Bot):
        self._server_management: Dict[int, list[ServerSettings, Dict[int, Event]]] = {}
        # This is technically a circular dependency (which I hate), but it's the best thing I could think of
        self.bot: Bot = bot
        self.testing_mode = False

    def get_event(self, server_id: int, channel_id: int) -> Event:
        if server_id in self._server_management:
            if channel_id in self._server_management[server_id]:
                return self._server_management[server_id][channel_id]
            else:
                channel = self.bot.get_channel(channel_id)
                # Technically, we should handle a possible error if channel is None here...
                if self.testing_mode:
                    event = TestEvent(server_id, channel)
                else:
                    event = Event(server_id, channel)
                self._server_management[channel_id] = event
                return event
        else:
            channel = self.bot.get_channel(channel_id)
            # Technically, we should handle a possible error if channel is None here...
            if self.testing_mode:
                event = TestEvent(server_id ,channel)
            else:
                event = Event(server_id, channel)
            self._server_management[channel_id] = event
            return event

    def get_mogilist_str(self, message: Message) -> str:
        mogi_lists = ""
        active_mogis, full_mogis = 0, 0
        if len(self._server_management[message.guild.id]) == 0:
            to_send = "There currently no active mogis.\n\n"
        else:
            for event_id, event in self._server_management[message.guild.id].items():
                if not len(event.queue_flat) == 0:
                    active_mogis+=1
                    line = f"<#{event_id}> - {str(len(event.queue_flat))}/12"
                    
                    if event.full:
                        full_mogis += 1
                        time_since_filled = datetime.now() - event.fill_time
                        time_since_filled = int(time_since_filled.total_seconds() // 60)
                        event_format = str(event.team_size) + 'v' + str(event.team_size)
                        line += f" - {event_format} - {time_since_filled}m ago"
                        
                    if message.channel.name[-2:] == "lu":
                        line += "\n" + ", ".join(event.queue_flat)
                    mogi_lists += line + "\n\n"
            to_send = f"There are {active_mogis} active mogi and {full_mogis} full mogi.\n\n{mogi_lists}"
        to_send += f"Last updated at <t:{str(int(current_unix_epoch_timestamp()))}:T>\nThis will update every 30 seconds."
        return to_send

    async def remove_players_from_all_lineups(self, ctx: ApplicationContext, players: List[str], filled_channel_id: int):
        for channel_id, event in self._server_management[ctx.guild.id].items():
            if channel_id == filled_channel_id:
                continue

            removed_players = []
            for player in players:
                removed_players_to_append = await event.find_and_remove_player(ctx, player)
                removed_players.extend([p.display_name for p in removed_players_to_append])

            if len(removed_players) != 0:
                await event.channel.send(
                    f"{', '.join(removed_players)} has been removed from the lineup due to a mogi filling in <#{filled_channel_id}>")

    async def can(self, ctx: ApplicationContext, partners: List[str]):
        event = self.get_event(ctx.channel.id)
        added = await event.can(ctx, partners)
        # event could fill up after this. if this happens, we want to call remove_players_from_all_lineups and
        # event.event_full
        if event.full and event.queue_num == 12 and added > 0:
            await self.remove_players_from_all_lineups(ctx, event.queue_flat[:12], event.channel.id)
            await event.event_full(ctx)

    async def end_mogi(self, ctx: ApplicationContext):
        event = self.get_event(ctx.channel.id)
        if not event.active:
            await ctx.send("There is no mogi currently active in this channel, use !start to begin one.")
            return

        is_mod = is_moderator(ctx)
        if not event.full:
            if not is_mod:
                return
        elif datetime.now() - event.fill_time < timedelta(minutes=40) and not is_mod:
            # do not allow the mogi to end if the caller is not a mod & it's been less than 40 minutes
            return
        elif timedelta(minutes=40) < datetime.now() - event.fill_time < timedelta(
                minutes=60) and ctx.message.author.display_name not in event.queue_flat and not is_mod:
            # do not allow the mogi to end if it's been between 40 and 60 minutes and the caller is not in the mogi
            return

        await ctx.send("The mogi has ended. You can use `!s` to start a new one.")
        del self._server_management[ctx.guild.id][ctx.channel.id]

    async def activity_check(self):
        for server_id in self._server_management.keys():
            for channel_id in self._server_management[server_id]:
                channel = self.bot.get_channel(channel_id)
                event = self.get_event(server_id, channel_id)
                await event.notify_and_remove(channel)

    async def mogilist(self, mogilist_sticky_messages: List[Message]):
        for message in mogilist_sticky_messages:
            message_str = self.get_mogilist_str(message)
            await message.edit(content=message_str)
