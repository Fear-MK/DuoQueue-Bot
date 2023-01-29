import asyncio

from discord import Bot, ApplicationContext
from discord.ext import commands

from model.eventmanager import EventManager
from utils import is_moderator


class Mogi(commands.Cog):
    """
    All mogi related commands go in here. This includes:
        - start
        - end
        - next
        - esn
        - ping
        - remove
        - can
        - drop
        - lineup
        - s
        -
    """

    def __init__(self, bot: Bot, event_manager: EventManager):
        self.bot = bot
        self._event_manager = event_manager

    @commands.command()
    async def start(self, ctx: ApplicationContext):
        event = self._event_manager.get_event(ctx.channel.id)
        await event.start_mogi(ctx)

    @commands.command()
    async def end(self, ctx: ApplicationContext):
        event = self._event_manager.get_event(ctx.channel.id)
        await event.end_mogi(ctx)

    @commands.command()
    async def next(self, ctx: ApplicationContext):
        event = self._event_manager.get_event(ctx.channel.id)
        await event.next(ctx)

    @commands.command(aliases=["esn"])
    async def endstartnext(self, ctx: ApplicationContext):
        event = self._event_manager.get_event(ctx.channel.id)
        await asyncio.gather(event.end_mogi(ctx), asyncio.sleep(1))
        await event.start_mogi(ctx)
        await event.next(ctx)

    @commands.command(aliases=["p"])
    @commands.cooldown(1, 900, commands.BucketType.channel)
    async def ping(self, ctx: ApplicationContext, number: int = 0):
        event = self._event_manager.get_event(ctx.channel.id)
        await event.ping(ctx, number)

    @commands.command(aliases=["r"])
    async def remove(self, ctx: ApplicationContext, number: int = -1):
        if not is_moderator(ctx):
            await ctx.send("You must be a moderator to use this command.")
        if number == -1:
            await ctx.send("You need to specify a number indicated by `!l`.")
            return
        event = self._event_manager.get_event(ctx.channel.id)
        msg = await event.remove(ctx, number)
        await ctx.send(msg)

    @commands.command(aliases=["c"])
    async def can(self, ctx: ApplicationContext):
        event = self._event_manager.get_event(ctx.channel.id)
        if ctx.message.mentions:
            await event.can(ctx, [mentioned.display_name for mentioned in ctx.message.mentions])
        else:
            await event.can(ctx, [])

    @commands.command(aliases=["d"])
    async def drop(self, ctx: ApplicationContext):
        event = self._event_manager.get_event(ctx.channel.id)
        await event.drop(ctx)

    @commands.command(aliases=["list", "l"])
    @commands.cooldown(1, 30, commands.BucketType.channel)
    async def lineup(self, ctx: ApplicationContext):
        event = self._event_manager.get_event(ctx.channel.id)
        await event.lineup(ctx, True)

    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def s(self, ctx: ApplicationContext):
        event = self._event_manager.get_event(ctx.channel.id)
        await event.lineup(ctx, False)

    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def teams(self, ctx: ApplicationContext):
        event = self._event_manager.get_event(ctx.channel.id)
        await event.teams(ctx)

    @commands.command(aliases=["ul"])
    @commands.cooldown(1, 15)
    async def unconfirmedlineup(self, ctx: ApplicationContext):
        event = self._event_manager.get_event(ctx.channel.id)
        await event.unconfirmed_lineup(ctx)


def setup(bot: Bot):
    # this is kind of janky, but we need to inject event_manager into this. so we construct it in main
    # instead of here
    print("mogi cog loaded!")
    pass
