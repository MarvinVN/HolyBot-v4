import discord
from discord.ext import commands
import json
import os

def read_token():
    with open('./token.txt', 'r') as f:
        lines = f.readlines()
        return lines[0].strip()

intents = discord.Intents().all()
token = read_token()
client = commands.Bot(command_prefix='$', intents=intents)

@client.event
async def on_ready():
    print('HolyBot v4 ready')

@client.event
async def on_guild_join(guild):
    with open('servers.json', 'r') as f:
        servers = json.load(f)

    servers[str(guild.id)] = {}

    servers[str(guild.id)]['prefix'] = '$'
    servers[str(guild.id)]['autorole'] = 0

    with open('servers.json', 'w') as f:
        json.dump(servers, f, indent=4)

@client.event
async def on_guild_remove(guild):
    with open('servers.json', 'r') as f:
        servers = json.load(f)

    servers.pop(str(guild.id))

    with open('servers.json', 'w') as f:
        json.dump(servers, f, indent=4)

def get_autorole(guild):
    with open('servers.json', 'r') as f:
        servers = json.load(f)

    return servers[str(guild.id)]['autorole']

@client.event
async def on_member_join(member):
    await member.guild.text_channels[0].send(f'{member.name} has joined!')
    await member.add_roles(member.guild.get_role(get_autorole(member.guild)))

@client.command()
async def ping(ctx):
    await ctx.send('pong')

@client.command(aliases=['autorole'])
async def set_autorole(ctx, role:discord.Role):
    with open('servers.json', 'r') as f:
        servers = json.load(f)

    servers[str(ctx.guild.id)]['autorole'] = role.id

    with open('servers.json', 'w') as f:
        json.dump(servers, f, indent=4)

    await ctx.send(f'Autorole changed to *{ctx.guild.get_role(role.id)}*')

@set_autorole.error
async def autorole_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please include a role")
    elif isinstance(error, commands.RoleNotFound):
        await ctx.send("Role not found")

@client.command(aliases=['prefix'])
async def setprefix(ctx, prefixset='$'):
    if (not ctx.author.guild_permissions.manage_guild):
        await ctx.send("You do not have the required permissions")
        return

    with open('servers.json', 'r') as f:
        servers = json.load(f)

    servers[str(ctx.guild.id)]['prefix'] = prefixset

    with open('servers.json', 'w') as f:
        json.dump(servers, f, indent=4)

    client.command_prefix = prefixset
    await ctx.send(f"Prefix has been changed to *{prefixset}*")

@client.command()
async def kick(ctx, member:discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f'{member.mention} has been kicked')

@kick.error
async def kick_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please include a member")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("Member not found")

@client.command(aliases=['clear'])
async def purge(ctx, amount=2):
    if (not ctx.author.guild_permissions.manage_messages):
        await ctx.send("You do not have the required permissions")
        return
    if amount > 101:
        await ctx.send("Cannot delete more than 100 messages")
    else:
        await ctx.channel.purge(limit=amount+1)

client.run(token)

