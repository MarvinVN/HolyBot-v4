from nextcord import Interaction, SlashOption, ChannelType
from nextcord.abc import GuildChannel
from nextcord.ext import commands, tasks
from dotenv import load_dotenv
from utils.mongo import Document
import nextcord
import os
import motor.motor_asyncio
import utils.utils

intents = nextcord.Intents().all()
load_dotenv()
token = os.getenv("SECRET")
bot = commands.Bot(command_prefix='$', intents=intents)

db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASS")
cluster = motor.motor_asyncio.AsyncIOMotorClient(f"mongodb+srv://{db_user}:{db_pass}@cluster0.8uikimy.mongodb.net/?retryWrites=true&w=majority")

db_test = Document(cluster["HolyBot"], 'test')
db_servers = Document(cluster["HolyBot"], 'servers')
db_rankedwatch = Document(cluster["HolyBot"], 'rankedwatch')
db_player_cache = Document(cluster["HolyBot"], 'player_cache')

for file in os.listdir("./cogs"):
    if file.endswith(".py"):
        bot.load_extension(f"cogs.{file[:-3]}")

@bot.command()
async def load(ctx, extension):
    bot.load_extension(f"cogs.{extension}")
    await ctx.send("Loaded cog!")

@bot.command()
async def unload(ctx, extension):
    bot.unload_extension(f"cogs.{extension}")
    await ctx.send("Unloaded cog!")

@bot.command()
async def reload(ctx, extension):
    bot.reload_extension(f"cogs.{extension}")
    await ctx.send("Reloaded cog!")
    

@bot.event
async def on_ready():
    print('HolyBot v4 ready')

@bot.event
async def on_guild_join(guild):
    text_channel_id = str(utils.utils.get_first_valid_text_channel_id(guild))
    await db_servers.insert({"_id": guild.id, "autorole": text_channel_id, "rw_channel": text_channel_id})
    await db_rankedwatch.insert({"_id": guild.id})    

@bot.event
async def on_guild_remove(guild):
    await db_servers.delete(guild.id)

async def get_autorole(guild):
    data = await db_servers.find_by_id(guild.id)
    return data["autorole"]

@bot.event
async def on_member_join(member):
    await member.add_roles(member.guild.get_role(await get_autorole(member.guild)))

@bot.slash_command()
async def ping(interaction:Interaction):
    '''Pings the bot'''
    await interaction.response.send_message("Pong!")

bot.run(token)
