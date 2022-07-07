from nextcord import Interaction, SlashOption, ChannelType
from nextcord.abc import GuildChannel
from nextcord.ext import commands, tasks
import nextcord
import json
import aiosqlite
import os
from dotenv import load_dotenv

intents = nextcord.Intents().all()
load_dotenv()
token = os.getenv("SECRET")
client = commands.Bot(command_prefix='$', intents=intents)

for file in os.listdir("./cogs"):
    if file.endswith(".py"):
        client.load_extension(f"cogs.{file[:-3]}")

@client.command()
async def load(ctx, extension):
    client.load_extension(f"cogs.{extension}")
    await ctx.send("Loaded cog!")

@client.command()
async def unload(ctx, extension):
    client.unload_extension(f"cogs.{extension}")
    await ctx.send("Unloaded cog!")

@client.command()
async def reload(ctx, extension):
    client.reload_extension(f"cogs.{extension}")
    await ctx.send("Reloaded cog!")
    

@client.event
async def on_ready():
    print('HolyBot v4 ready')
    async with aiosqlite.connect('./database/main.db') as db:
        async with db.cursor() as cursor:
            await cursor.execute('CREATE TABLE IF NOT EXISTS servers (guildID INTEGER, autorole INTEGER, rankedwatch_channel)')
            await cursor.execute('CREATE TABLE IF NOT EXISTS rankedwatch (id INTEGER, guildID INTEGER, summonerName VARCHAR(16))')
        await db.commit()

@client.event
async def on_guild_join(guild):
    async with aiosqlite.connect('./database/main.db') as db:
        async with db.cursor() as cursor:
            await cursor.execute('INSERT INTO servers (guildID, autorole, rankedwatch_channel) VALUES (?, ?)', (guild.id, 0, 0,))
        await db.commit()

@client.event
async def on_guild_remove(guild):
    async with aiosqlite.connect('./database/main.db') as db:
        async with db.cursor() as cursor:
            await cursor.execute('DELETE FROM servers WHERE guildID = ?', (guild.id,))
            await cursor.execute('DELETE FROM rankedwatch WHERE guildID = ?', (guild.id,))
        await db.commit()

async def get_autorole(guild):
    async with aiosqlite.connect("./database/main.db") as db:
        async with db.cursor() as cursor:
            await cursor.execute('SELECT autorole FROM servers WHERE guildID = ?', (guild.id,))
            data = await cursor.fetchone()
            data = data[0]

    return data

@client.event
async def on_member_join(member):
    await member.guild.text_channels[0].send(f'{member.mention} has joined!')
    await member.add_roles(member.guild.get_role(await get_autorole(member.guild)))

@client.slash_command()
async def ping(interaction:Interaction):
    '''Pings the bot'''
    await interaction.response.send_message("Pong!")

client.run(token)
