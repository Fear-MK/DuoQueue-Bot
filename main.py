import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio
import random
from time import time as current_unix_epoch_timestamp

from secret import bot_key
from Shared import *

intents = discord.Intents.all()


bot = commands.Bot(command_prefix='!', intents=intents, help_command=None, case_insensitive=True)

events={}
mogilist_sticky_messages=[]


def get_event(channel_id):
    if channel_id in events:
        return events[channel_id]
    else:
        event = Event(channel_id)
        events[channel_id] = event
        return event

def is_moderator(ctx):
    if any(x in [role.name for role in ctx.author.roles] for x in moderator_roles):
        return True
    else:
        return False

def get_lineup_str(queue):
    if len(queue) == 0:
        return ""
    string=""
    increase=0
    for i, item in enumerate(queue, start=1):
        x=i+increase
        if isinstance(item, list):
            increase+=1
            balls=str(item).replace("'", "")[1:-1]
            string+=f"`{str(x)}, {str(x+1)}. ` {balls}\n"
        else:
            string+=f"`{x}.`  {item}\n"
    return string

def get_teams_string(teams):
    output="**Format: 2v2**\n\n"
    for i, item in enumerate(teams, start=1):
        output+=f"`Team {i}`: {', '.join(item)}\n"
    output+=f"Table: `!scoreboard {', '.join([j for sub in teams for j in sub])}`"
    return output

def fetch_user_objs(ctx, names):
        objects=[]
        for name in names:
            objects.append(discord.utils.get(ctx.guild.members, display_name=name))
        return objects

async def create_sticky_messages():
    for id in [mogilist_id, mogilist_lu_id]:
        channel = bot.get_channel(id)
        await channel.purge()
        message = await channel.send("There are no mogis active currently.")
        mogilist_sticky_messages.append(message)
    mogilist.start()

def get_mogilist_str(message):
    to_send=""
    mogi_lists=""
    full_mogis=0
    if len(events) == 0:
        to_send+="There currently no active mogis.\n\n"
    else:
        for event_id, event in events.items():
            if not len(event.queue_flat) == 0:
                line=f"<#{event_id}> - {str(len(event.queue_flat))}/12"
                if event.full:
                    full_mogis+=1
                    time_since_filled = datetime.now()-event.fill_time
                    time_since_filled = time_since_filled.total_seconds()//60
                    event_format = str(event.team_size)+'v'+str(event.team_size)
                    line += f" - {event_format} - {time_since_filled}"
                if message.channel.name[-2:] == "lu":
                    line+="\n"+", ".join(event.queue_flat)
            mogi_lists+=line+"\n\n"
        to_send+=f"There are {len(events)} active mogi and {full_mogis} full mogi.\n\n{mogi_lists}"
    to_send+=f"Last updated at <t:{int(current_unix_epoch_timestamp())}:T>\nThis will update every 30 seconds."
    return to_send

async def remove_players_from_all_lineups(players, channel_id):
    for id in list(events.keys()):
        event = get_event(id)
        queue_flat, unconfirmed_flattened=event.queue_flat, event.unconfirmed_flattened #requires static array
        removed_players=[]
        removed_unconfirmed_players=[]
        for player in players:
            if player in queue_flat[:12] and event.full:
                pass

            elif (player in queue_flat[12:]) or (player in queue_flat and not event.full):
                await event.remove(event.channel, event.queue_flat.index(player)+1, True)
                removed_players.append(player)
                
            elif player in unconfirmed_flattened:
                await event.remove_team_unconfirmed(player)
                removed_unconfirmed_players.append(player)
            else:
                print(player+" not found")

        if len(removed_unconfirmed_players)!=0:
            await event.channel.send(f"{', '.join(removed_unconfirmed_players)} has been removed from unconfirmed squads due to a mogi filling in <#{channel_id}>")

        if len(removed_players)!=0:
            await event.channel.send(f"{', '.join(removed_players)} has been removed from the lineup due to a mogi filling in <#{channel_id}>")


class Event:
    def __init__(self, channel_id):
        self.active = False
        self.full = False
        self.team_size = 2
        self.teams_per_room = 6

        self.queue = []
        self.queue_flat = []
        self.queue_num = 0
        self.unconfirmed_squads = []
        self.unconfirmed_flattened = []

        self.waiting_for_response = []

        self.teams = []

        self.channel = bot.get_channel(channel_id)
        self.is_primary_leaderboard = True #RT/CT
        self.leaderboard_type_str = None
        self.fill_time = None

    #NON-DISCORD FUNCTIONS

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
                return True
        return None

    async def remove_team_unconfirmed(self, name):
        squads=[list(d.keys()) for d in self.unconfirmed_squads]
        for i, array in enumerate(squads):
            if name in array:
                arr=array
                index = i
                break
        else:
            return
        del self.unconfirmed_squads[index]
        self.unconfirmed_flattened = [x for x in self.unconfirmed_flattened if x not in arr]

    async def update_queue_num(self, ctx, number):
        if self.queue_num+number == 12 and not self.queue_num > 12:
            self.queue_num+=number
            await self.event_full(ctx)
        else:
            self.queue_num+=number

    #DISCORD PROCESSES

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
        inactive_users=[]

        for user in self.queue_flat:
            if user in self.waiting_for_response:
                pass
            last_message_time = await self.get_last_message_time(user)

            if current_time - last_message_time >= timedelta(minutes=30):
                inactive_users.append(user)
                self.waiting_for_response.append(user)

                await channel.send(f"{user}, please type something in the chat in the next 5 minutes to keep your spot in the mogi")

                await asyncio.sleep(300)

                last_message_time = await self.get_last_message_time(user)

                if current_time - last_message_time >= timedelta(seconds=5):
                    await self.remove(channel, self.queue_flat.index(user)+1, True)

    async def event_full(self, ctx):
        self.full=True
        fill_time=datetime.now()
        self.fill_time = fill_time
        solo_players=[]
        team_players=[]

        await remove_players_from_all_lineups(self.queue_flat[:12], self.channel.id)

        player_objs = fetch_user_objs(ctx, self.queue_flat[:12])
        await ctx.send(f"There are 12 players in the mogi.\nType `!l` to get a list of the current lineup.\n\n{', '.join([user.mention for user in player_objs])} Mogi has 12 players")

        for team in self.queue:
            if not isinstance(team, list):
                solo_players.append(team)
            else:
                team_players.append(team)
        
        random.shuffle(solo_players)

        solo_player_teams=[list(group) for group in zip(*[iter(solo_players)]*self.team_size)]

        completed_teams=solo_player_teams+team_players

        await ctx.send(f"{get_teams_string(completed_teams)}\n\nDecide a host amongst yourselves.")



    #DISCORD COMMANDS BEGIN

    async def start_mogi(self, ctx):
        if self.active == True:
            await ctx.send("You must end the current event before starting a new one.")
            return
        self.active = True
        await ctx.send(f"A new {str(self.team_size)}v{str(self.team_size)} mogi has started, type !c to join solo, or tag a partner to join as a team.")

    async def end_mogi(self, ctx):
        if self.active == False:
            await ctx.send("There is no mogi currently active in this channel, use !start to begin one.")
            return
        
        if datetime.now()-self.start_time < timedelta(minutes=40) and not any(x in [role.name for role in ctx.author.roles] for x in moderator_roles):
            return
        
        elif datetime.now()-self.start_time > timedelta(minutes=40) and datetime.now()-self.start_time < timedelta(minutes=60) and not ctx.author.name in self.queue_flat:
            return
        
        self.active = False
        self.queue = []
        self.queue_flat = []

        await ctx.send("The current mogi has been ended")
    
    async def next(self, ctx):
        if not is_moderator(ctx):
            return

        await ctx.send("@ here A mogi has started. Type `!c` if not currently playing")

    async def ping(self, ctx, number):
        if number == None or number == "":
            number = 12-len(self.queue_flat)

        if number > 6:
            return
        else:
            await ctx.message.delete()
            await ctx.send(f"@ here +{number}")

    async def lineup(self, ctx, permanent):
        lineup_str=get_lineup_str(self.queue)
        if permanent:
            await ctx.send(f"`Mogi List`\n{lineup_str}\nYou can use `!l` again in 30 seconds" if lineup_str != "" else "There are no players in the mogi.")
        else:
            msg = await ctx.send(f"`Mogi List`\n{lineup_str}\n" if lineup_str != "" else "There are no players in the mogi.")
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
    
    async def can(self, ctx, partners):
        if not self.active:
            await ctx.send("There is no mogi currently active in this channel, use !start to begin one.")
            return

        if self.queue_num == 15:
            await ctx.send("Unable to join the mogi. The mogi currently has 15 players.")

        name=ctx.message.author.display_name
        partners.append(name)
        squad=partners

        if name in self.queue_flat:
            await ctx.send()

        if len(partners) < 2:
            checkList = self.check_list([name])
            if checkList == True:
                await ctx.send(f"{name} is already in the mogi. {str(self.queue_num)} players are in the mogi.")
                return
            
            elif name in self.unconfirmed_flattened:
                await ctx.send(f"You are in an unconfirmed squad. Check the unconfirmed squads with `!ul` and type `!c @partner` or `!d` to remove yourself from the unconfirmed list.")

            else:
                self.queue.append(name)
                self.queue_flat.append(name)
                await ctx.send(f"{name} has joined the mogi. {str(self.queue_num+1)} players are in the mogi.")
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
                await ctx.send("One of the players in your squad is in an unconfirmed squad, please drop before trying the command again.")
                return

            if checkWaiting == None: #Neither are queued
                self.unconfirmed_squads.append({squad[-1]: "Confirmed", squad[0]: "Unconfirmed"})
                self.unconfirmed_flattened.extend(squad)
                await ctx.send(f"Created a squad with {squad[-1]} and {squad[0]}. {squad[0]} must type `!c @{squad[-1]}` to join the mogi.")
                return

            if isinstance(checkWaiting, dict):
                unconfirmed_squad=checkWaiting
                if unconfirmed_squad[name] == "Confirmed":
                    await ctx.send("You are already confirmed. Your partner must type `!c @Your Name`")
                    return
                else:
                    self.queue.append(squad)
                    self.queue_flat.extend(squad)

                    await ctx.send(f"Squad confirmed: `{', '.join(squad)}`. {str(self.queue_num+2)} players are in the mogi.")

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
                        team=item
                        user=fetch_user_objs(ctx, [item[1]] if item[0] == name else [item[0]])
                        await ctx.send(f"{user[0].mention}, your teammate has dropped from the lineup.")
                        del self.queue[i]
                        await self.update_queue_num(ctx, -2)
                        break
            else:
                team=[name]
                self.queue.remove(name)
                await self.update_queue_num(ctx, -1)
            self.queue_flat=[x for x in self.queue_flat if x not in team]
            await ctx.send(f"{name} and has dropped from the mogi. {str(self.queue_num)} players remaining in the mogi.")       
                
        else:
            await ctx.send(f"{name} is already dropped from the mogi {str(self.queue_num)} players remaining in the mogi.")

    async def remove(self, channel, number, bypass):
        if bypass:
            pass
        elif not is_moderator(channel): #so the bot can use this function
            await channel.send("You must be a moderator to use this command.")

        if not self.active:
            await channel.send("There is no mogi currently active in this channel, use `!start` to begin one.")
            return      

        if number == None: #If !r has no arguments
            await channel.send(f"{get_lineup_str(self.queue)}\nTo remove the 4th player on the list, use `!r 4`")

        number=int(number)

        if number > len(self.queue_flat) or number < 1:
            await channel.send("That number is not on the list. Use `!l` to see the players to remove")

        name=self.queue_flat[number-1]
        for i, item in enumerate(self.queue):
            if isinstance(item, list):
                if name in item:
                    team=item
                    users=fetch_user_objs(channel, item)
                    del self.queue[i]
                    await self.update_queue_num(channel, -2)
                    break
        else:
            team = [name]
            users= fetch_user_objs(channel, [name])
            self.queue.remove(name)
            await self.update_queue_num(channel, -1)
        self.queue_flat=[x for x in self.queue_flat if x not in team]
        if not bypass:
            await channel.send(f"{', '.join([user.mention for user in users])} has been removed from the mogi. {str(len(self.queue_flat))} players remaining.") 

@tasks.loop(seconds=30)
async def mogilist():
    for message in mogilist_sticky_messages:
        message_str=get_mogilist_str(message)
        await message.edit(content=message_str)    

@tasks.loop(seconds=15)
async def activity_check():
    for id in list(events.keys()):
        channel = bot.get_channel(id)
        event = get_event(id)
        await event.notify_and_remove(channel)

@bot.command()
async def start(ctx):
    event = get_event(ctx.channel.id)
    await event.start_mogi(ctx)

@bot.command()
async def end(ctx):
    event = get_event(ctx.channel.id)
    await event.end_mogi(ctx)

@bot.command()
async def next(ctx):
    event = get_event(ctx.channel.id)
    await event.next(ctx)

@bot.command(aliases=["esn"])
async def endstartnext(ctx):
    event = get_event(ctx.channel.id)
    await event.end_mogi(ctx)
    await event.start_mogi(ctx)
    await event.next(ctx)

@bot.command(aliases=["p"])
@commands.cooldown(1, 900, commands.BucketType.channel)
async def ping(ctx, number):
    event = get_event(ctx.channel.id)
    await event.ping(ctx, number)

@bot.command(aliases=["r"])
async def remove(ctx, number):
    if not number.isdigit():
        number=None
    event = get_event(ctx.channel.id)
    await event.remove(ctx, number, False)

@bot.command(aliases=["c"])
async def can(ctx):
    event = get_event(ctx.channel.id)
    if ctx.message.mentions:
        await event.can(ctx, [mentioned.display_name for mentioned in ctx.message.mentions])
    else:
        await event.can(ctx, [])

@bot.command(aliases=["d"])
async def drop(ctx):
    event = get_event(ctx.channel.id)
    await event.drop(ctx)

@bot.command(aliases=["list", "l"])
@commands.cooldown(1, 30, commands.BucketType.channel)
async def lineup(ctx):
    event = get_event(ctx.channel.id)
    await event.lineup(ctx, True)


@bot.command()
@commands.cooldown(1, 15, commands.BucketType.channel)
async def s(ctx):
    event = get_event(ctx.channel.id)
    await event.lineup(ctx, False)

@bot.command(aliases=["ul"])
@commands.cooldown(1,15)
async def unconfirmedlineup(ctx):
    event = get_event(ctx.channel.id)
    await event.unconfirmed_lineup(ctx)    

@bot.event
async def on_ready():
    await create_sticky_messages()
    activity_check.start()

print("Bot Started")
bot.run(bot_key)