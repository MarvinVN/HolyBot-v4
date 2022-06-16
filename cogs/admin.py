from nextcord import Interaction, Permissions
from nextcord.ext import commands, tasks
import nextcord
import aiosqlite
from bot import testingServerID, client
from itertools import cycle

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

    @nextcord.slash_command(default_member_permissions=Permissions(administrator=True), guild_ids=[testingServerID])
    async def autorole(self, interaction:Interaction, role:nextcord.Role):
        '''Sets a role to be automatically given to a member once they join the server'''

        if (not interaction.user.guild_permissions.manage_guild):
            await interaction.response.send_message("You do not have the required permissions")
            return

        async with aiosqlite.connect("./database/main.db") as db:
            async with db.cursor() as cursor:
                await cursor.execute('SELECT autorole FROM servers WHERE guildID = ?', (interaction.guild_id,))
                data = await cursor.fetchone()
                data = data[0]
                if data:
                    await cursor.execute('UPDATE servers SET autorole = ? WHERE guildID = ?', (role.id, interaction.guild_id,))
                else:
                    await cursor.execute('INSERT INTO servers (guildID, autorole) VALUES (?, ?)', (interaction.guild_id, role.id,))
            await db.commit()
        await interaction.response.send_message(f'Autorole changed to *{interaction.guild.get_role(role.id)}*')

    @nextcord.slash_command(default_member_permissions=Permissions(kick_members=True), guild_ids=[testingServerID])
    async def kick(self, interaction:Interaction, member:nextcord.Member, *, reason=None):
        '''Kicks a member from the server'''

        if (not interaction.user.guild_permissions.kick_members):
            await interaction.response.send_message("You do not have the required permissions")
            return
        
        await member.kick(reason=reason)
        await interaction.response.send_message(f'{member.mention} has been kicked')

    @nextcord.slash_command(default_member_permissions=Permissions(manage_messages=True), guild_ids=[testingServerID])
    async def purge(self, interaction:Interaction, amount:int):
        '''Clears a given amount of the most recent messages from the chat'''

        if (not interaction.user.guild_permissions.manage_messages):
            await interaction.response.send_message("You do not have the required permissions")
            return
        if amount > 101:
            await interaction.response.send_message("Cannot delete more than 100 messages")
        else:
            await interaction.channel.purge(limit=amount+1)
            await interaction.response.send_message(f"**{amount}** messages purged.")

def setup(bot):
    bot.add_cog(Admin(bot))
    