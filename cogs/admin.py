from discord import Bot, ApplicationContext
from discord.ext import commands
from model.serversettings import ServerSettings

class Admin(commands.Cog):
    """All administrator/server setting commands go here

    - set_sticky_ids
    - disabling/enabling the bot for the server(?)
    - automatically end a mogi after x time
    """

    def __init__(self, bot: Bot, server_settings: ServerSettings):
        self.bot = bot
        self.settings = server_settings

    @commands.command()
    async def set_sticky_ids(self, ctx: ApplicationContext, mogilist_id: int, mogilist_lu_id: int):
        