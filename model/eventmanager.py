from datetime import datetime, timedelta
from typing import List, Dict
from discord import Bot, Message, ApplicationContext
from model.event import Event
from time import time as current_unix_epoch_timestamp
from test.testevent import TestEvent
from utils import is_moderator


class EventManager:

    def __init__(self, bot: Bot):
        self._events: Dict[int, Event] = {}
        # This is technically a circular dependency (which I hate), but it's the best thing I could think of
        self.bot: Bot = bot
        self.testing_mode = False

    def get_event(self, channel_id: int) -> Event:
        if channel_id in self._events:
            return self._events[channel_id]
        else:
            channel = self.bot.get_channel(channel_id)
            # Technically, we should handle a possible error if channel is None here...
            if self.testing_mode:
                event = TestEvent(channel)
            else:
                event = Event(channel)
            self._events[channel_id] = event
            return event

    def get_mogilist_str(self, message: Message) -> str:
        mogi_lists = ""
        full_mogis = 0
        if len(self._events) == 0:
            to_send = "There currently no active mogis.\n\n"
        else:
            for event_id, event in self._events.items():
                if not len(event.queue_flat) == 0:
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
            to_send = f"There are {len(self._events)} active mogi and {full_mogis} full mogi.\n\n{mogi_lists}"
        to_send += f"Last updated at <t:{str(int(current_unix_epoch_timestamp()))}:T>\nThis will update every 30 seconds."
        return to_send

    async def remove_players_from_all_lineups(self, ctx: ApplicationContext, players: List[str],
                                              filled_channel_id: int):
        for channel_id, event in self._events.items():
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
                await ctx.send("You must get a moderator to end the mogi, as it is not full.")
                return
        elif datetime.now() - event.fill_time < timedelta(minutes=40) and not is_mod:  # should be 40 mins
            # do not allow the mogi to end if the caller is not a mod & it's been less than 40 minutes
            return
        elif timedelta(minutes=40) < datetime.now() - event.fill_time < timedelta(
                minutes=60) and ctx.message.author.display_name not in event.queue_flat and not is_mod:
            # do not allow the mogi to end if it's been between 40 and 60 minutes and the caller is not in the mogi
            return

        await ctx.send("The mogi has ended. You can use `!s` to start a new one.")
        self._events.pop(ctx.channel.id)

    async def activity_check(self):
        for channel_id in self._events.keys():
            channel = self.bot.get_channel(channel_id)
            event = self.get_event(channel_id)
            await event.notify_and_remove(channel)

    async def mogilist(self, mogilist_sticky_messages: List[Message]):
        for message in mogilist_sticky_messages:
            message_str = self.get_mogilist_str(message)
            await message.edit(content=message_str)
