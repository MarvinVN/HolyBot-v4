from nextcord import Interaction, SlashOption, ChannelType
from nextcord.abc import GuildChannel
from nextcord.ext import commands, tasks
import nextcord
import json
from itertools import cycle
import aiosqlite

def read_token():
    with open('./token.txt', 'r') as f:
        lines = f.readlines()
        return lines[0].strip()

testingServerID = 216653732526424065 #only used for production, take out of slash command arguments once fully implemented

intents = nextcord.Intents().all()
token = read_token()
client = commands.Bot(command_prefix='$', intents=intents)

status = cycle([
    'you 👀',
    'the Minecraft movie',
    'BBC'
])

@client.event
async def on_ready():
    print('HolyBot v4 ready')
    async with aiosqlite.connect('main.db') as db:
        async with db.cursor() as cursor:
            await cursor.execute('CREATE TABLE IF NOT EXISTS servers (guildID INTEGER, autorole INTEGER)')
        await db.commit()
    status_swap.start()

@tasks.loop(seconds=1800)
async def status_swap():
    await client.change_presence(activity=nextcord.Activity(type=nextcord.ActivityType.watching, name=next(status)))

@client.event
async def on_guild_join(guild):
    async with aiosqlite.connect('main.db') as db:
        async with db.cursor() as cursor:
            await cursor.execute('INSERT INTO servers (guildID, autorole) VALUES (?, ?)', (guild.id, 0,))
        await db.commit()

@client.event
async def on_guild_remove(guild):
    async with aiosqlite.connect('main.db') as db:
        async with db.cursor() as cursor:
            await cursor.execute('DELETE FROM servers WHERE guildID = ?', (guild.id,))
        await db.commit()

async def get_autorole(guild):
    async with aiosqlite.connect("main.db") as db:
        async with db.cursor() as cursor:
            await cursor.execute('SELECT autorole FROM servers WHERE guildID = ?', (guild.id,))
            data = await cursor.fetchone()
            data = data[0]

    return data

@client.event
async def on_member_join(member):
    await member.guild.text_channels[0].send(f'{member.name} has joined!')
    await member.add_roles(member.guild.get_role(get_autorole(member.guild)))

@client.slash_command(guild_ids=[testingServerID])
async def ping(interaction:Interaction):
    await interaction.response.send_message("Pong!")

@client.slash_command(guild_ids=[testingServerID])
async def autorole(interaction:Interaction, role:nextcord.Role):

    if (not interaction.user.guild_permissions.manage_guild):
        await interaction.response.send_message("You do not have the required permissions")
        return

    async with aiosqlite.connect("main.db") as db:
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

@client.slash_command(guild_ids=[testingServerID])
async def kick(interaction:Interaction, member:nextcord.Member, *, reason=None):

    if (not interaction.user.guild_permissions.kick_members):
        await interaction.response.send_message("You do not have the required permissions")
        return
    
    await member.kick(reason=reason)
    await interaction.response.send_message(f'{member.mention} has been kicked')

@client.slash_command(guild_ids=[testingServerID])
async def purge(interaction:Interaction, amount:int):
    if (not interaction.user.guild_permissions.manage_messages):
        await interaction.response.send_message("You do not have the required permissions")
        return
    if amount > 101:
        await interaction.response.send_message("Cannot delete more than 100 messages")
    else:
        await interaction.channel.purge(limit=amount+1)
        await interaction.response.send_message(f"**{amount}** messages purged.")

client.run(token)
