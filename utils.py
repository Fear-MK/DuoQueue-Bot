from typing import List

import discord
from discord import ApplicationContext, Member

from Shared import moderator_roles


def is_moderator(ctx: ApplicationContext) -> bool:
    member = ctx.author
    # this check is here for type safety; users do not have the roles attribute
    if not isinstance(member, Member):
        return False

    if any(x in [role.name for role in member.roles] for x in moderator_roles):
        return True
    else:
        return False


def get_lineup_str(queue: List[str | List[str]]) -> str:
    if len(queue) == 0:
        return ""
    string = ""
    increase = 0
    for i, item in enumerate(queue, start=1):
        x = i + increase
        if isinstance(item, list):
            increase += 1
            balls = str(item).replace("'", "")[1:-1]
            string += f"`{str(x)}, {str(x + 1)}. ` {balls}\n"
        else:
            string += f"`{x}.`  {item}\n"
    return string


def get_teams_string(teams: List[List[str]]) -> str:
    output = "**Format: 2v2**\n\n"
    for i, item in enumerate(teams, start=1):
        output += f"`Team {i}`: {', '.join(item)}\n"
    output += f"Table: `!scoreboard {', '.join([j for sub in teams for j in sub])}`"
    return output


def fetch_user_objs(ctx: ApplicationContext, names: List[str]) -> List[Member]:
    objects: List[Member] = []
    for name in names:
        member = discord.utils.get(ctx.guild.members, display_name=name)
        if member:
            objects.append(member)
    return objects
