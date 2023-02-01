import sys
from typing import List
import discord
from discord import Message
from discord.ext import commands, tasks
from Shared import mogilist_id, mogilist_lu_id
from cogs.mogi import Mogi
from model.eventmanager import EventManager
from secret import bot_key

intents = discord.Intents.all()

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None, case_insensitive=True)
event_manager: EventManager = EventManager(bot)
if len(sys.argv) == 2 and sys.argv[1] == "--test":
    print("testing mode active")
    event_manager.testing_mode = True

mogilist_sticky_messages: List[Message] = []
DEV_BOT_SPAM_CHANNEL_ID = 1011055865895329918


async def create_sticky_messages():
    """
    This method is called once in on_ready. It's used to initialize sticky messages in two channels. These messages
    are edited in mogilist, which is called every 30 seconds.
    """
    for channel_id in [mogilist_id, mogilist_lu_id]:
        channel = bot.get_channel(channel_id)
        try:
            sticky_message = await channel.fetch_message(channel.last_message_id)
            await sticky_message.edit(content="There are no mogis active currently.")
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            # Forbidden can occur if the most recent message was not the bot's. In this case, just make a new one.
            sticky_message = await channel.send("There are no mogis active currently.")
        mogilist_sticky_messages.append(sticky_message)


@tasks.loop(seconds=30)
async def mogilist():
    await event_manager.mogilist(mogilist_sticky_messages)


@tasks.loop(seconds=15)
async def activity_check():
    await event_manager.activity_check()


@bot.event
async def on_ready():
    await create_sticky_messages()
    mogilist.start()
    activity_check.start()
    embed_var = discord.Embed(title="Bot is now running", colour=discord.Color.green())
    embed_var.set_author(
        name=f'DuoQueue Bot',
    )
    channel = bot.get_channel(DEV_BOT_SPAM_CHANNEL_ID)  # dev-bot-spam
    await channel.send(embed=embed_var)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CommandNotFound):
        return
    if isinstance(error, commands.errors.MissingAnyRole):
        await ctx.send(error)
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send("This command is on cooldown.")
        return

    else:
        await ctx.send(
            f"An unknown error occurred. Please check <#1068047135284662332> and message Fear if the error is not there")
        embedVar = discord.Embed(url=ctx.message.jump_url, title=error, colour=discord.Color.red())
        embedVar.set_author(
            name=f'Channel: {ctx.channel.name}',
        )
        channel = bot.get_channel(DEV_BOT_SPAM_CHANNEL_ID)  # dev-bot-spam
        await channel.send(embed=embedVar)


# this is janky but somewhat necessary to inject event_manager into the cog
bot.load_extension('cogs.mogi')
mogi_cog = Mogi(bot, event_manager)
bot.add_cog(mogi_cog)
bot.run(bot_key)
