from nextcord import Interaction, Permissions, SlashOption
from nextcord.ext import commands, tasks
from itertools import cycle
from bot import db_servers
import nextcord

status = cycle([
    'you 👀',
    'the Minecraft movie',
    'BBC'
    ])

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.status_swap.start()

    @tasks.loop(minutes=30)
    async def status_swap(self):
        await self.bot.change_presence(activity=nextcord.Activity(type=nextcord.ActivityType.watching, name=next(status)))

    @nextcord.slash_command(default_member_permissions=Permissions(administrator=True))
    async def autorole(self, interaction:Interaction, role:nextcord.Role=SlashOption(description="Role to be automatically given.")):
        '''Sets a role to be automatically given to a member once they join the server'''
        await db_servers.update({"_id": interaction.guild_id, "autorole": role.id})
        await interaction.response.send_message(f'Autorole changed to *{interaction.guild.get_role(role.id)}*')

    @nextcord.slash_command(default_member_permissions=Permissions(kick_members=True))
    async def kick(self, interaction:Interaction, member:nextcord.Member=SlashOption(description="Member to be kicked."), *, reason=None):
        '''Kicks a member from the server'''
        await member.kick(reason=reason)
        await interaction.response.send_message(f'{member.mention} has been kicked')

    @nextcord.slash_command(default_member_permissions=Permissions(manage_messages=True))
    async def purge(self, interaction:Interaction, amount:int=SlashOption(description="Amount of messages to be cleared. 100 maximum.", min_value=1, max_value=100)):
        '''Clears a given amount of the most recent messages from the chat'''
        await interaction.channel.purge(limit=amount+1)
        await interaction.response.send_message(f"**{amount}** messages purged.")

def setup(bot):
    bot.add_cog(Admin(bot))
    