from multiprocessing.sharedctypes import Value
from nextcord import Interaction, SlashOption, ChannelType
from nextcord.abc import GuildChannel
from nextcord.ext import commands, tasks, application_checks
import nextcord
import aiosqlite
import cassiopeia as cass
import os
from dotenv import load_dotenv
import random
import string

load_dotenv()
API_KEY = os.getenv("RIOT_API_KEY")
cass.set_riot_api_key(API_KEY)  # This overrides the value set in your configuration/settings.

class RankedWatch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        async with aiosqlite.connect('./database/main.db') as db:
            async with db.cursor() as cursor:
                await cursor.execute('CREATE TABLE IF NOT EXISTS players (summonerName VARCHAR(16), tier VARCHAR(12), division VARCHAR(3), LP INTEGER, lastmatch VARCHAR(255))')
                await cursor.execute('CREATE TABLE IF NOT EXISTS updated (summonerName VARCHAR(16), tier VARCHAR(12), division VARCHAR(3), LP INTEGER, lastmatch VARCHAR(255), win BOOL)')
            await db.commit()
        self.rankedwatch_loop.start()
    
    #development only
    @commands.command()
    async def randommatch(self, interaction:Interaction, summonername):
        newmatch = ''.join(random.choice(string.ascii_letters) for i in range(10))
        async with aiosqlite.connect("./database/main.db") as db:
            async with db.cursor() as cursor:
                await cursor.execute('UPDATE players SET lastmatch = ? WHERE summonerName = ?', (newmatch, summonername,))
            await db.commit()
        await interaction.send('Done')

    #development only
    @commands.command()
    async def purgeplayerlist(self, interaction:Interaction):
        '''Removes all players from player list'''
        async with aiosqlite.connect('./database/main.db') as db:
            async with db.cursor() as cursor:
                await cursor.execute('DELETE FROM players')
            await db.commit()
        print('All members removed from player list')


    def get_last_match(self, summoner:cass.Summoner)->cass.Match:
        match_history = cass.get_match_history(
            continent=summoner.region.continent,
            puuid=summoner.puuid,
            queue=cass.Queue.ranked_solo_fives,
        )
        return match_history[0]

    '''
    get_ranked_data() sometimes doesn't give the updated data. Probably to do with how the data pipeline works with cassiopeia/Riot API
    Ongoing issue, will find solution later
    '''
    def get_ranked_data(self, summoner:cass.Summoner):
        res = {
            'name': summoner.name,
            'tier': "",
            'division': "",
            'lp': 0
        }
        try:
            target = [entry for entry in summoner.league_entries.fives.league.entries if entry.summoner.name == summoner.name][0]
            res['tier'] = str(target.tier)
            res['division'] = str(target.division)
            res['lp'] = target.league_points
        except ValueError as e:
            if len(e.args) > 0:
                if e.args[0] == "Queue does not exist for this summoner.":
                    res['tier'] = "Unranked"
                    res['division'] = "N/A"
                #elif e.args[0] == "'RANKED_TFT_DOUBLE_UP' is not a valid Queue":
                print(e.args[0])
            else:
                raise e
        '''
        res = {
            'name': target.summoner.name,
            'tier': str(target.tier),
            'division': str(target.division),
            'lp': target.league_points
        }'''
        return res

    @tasks.loop(minutes=15)
    async def rankedwatch_loop(self):
        async with aiosqlite.connect("./database/main.db") as db:
            async with db.cursor() as cursor:

                await cursor.execute('SELECT guildID, rankedwatch_channel FROM servers')
                guilds = await cursor.fetchall()

                for guild_entry in guilds:
                    guild_id = guild_entry[0]
                    text_channel = guild_entry[1]

                    guild = self.bot.get_guild(guild_id)

                    if text_channel == 0:
                        for channel in guild.text_channels:
                            if channel.permissions_for(guild.me).send_messages:
                                text_channel = channel.id
                                break

                    embedVar = nextcord.Embed(title="Ranked Watch Results", color=0x4eceef)
                    embedVar.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/LoL_icon.svg/256px-LoL_icon.svg.png?20201029024159")
                    new_games = False

                    await cursor.execute('SELECT players.*, rankedwatch.id FROM players INNER JOIN rankedwatch ON rankedwatch.summonerName=players.summonerName')
                    players = await cursor.fetchall()
                    
                    for player in players:
                        name = player[0]
                        tier = player[1]
                        division = player[2]
                        lp = player[3]
                        lastmatch_id = player[4]
                        member = guild.get_member(player[5])

                        embed_name = embed_value = ''
                        summoner = cass.get_summoner(name=name, region="NA")

                        await cursor.execute('SELECT * FROM updated WHERE summonerName = ?', (name,))
                        data = await cursor.fetchone()
                        if data:
                            newmatch_id = data[4]
                            if newmatch_id == lastmatch_id:
                                continue
                            new_data = {
                                'tier': data[1],
                                'division': data[2],
                                'lp': int(data[3]),
                                'win': True if data[5] else False
                            }
                        else:
                            newmatch = self.get_last_match(summoner)
                            newmatch_id = str(newmatch.id)
                            if newmatch_id[:4] != "NA1_":
                                newmatch_id = "NA1_" + newmatch_id
                            if newmatch_id == lastmatch_id:
                                continue
                            new_data = self.get_ranked_data(summoner)
                            new_data['win'] = newmatch.participants[summoner.name].stats.win

                        new_games = True
                        result = change = ''
                        lp_gain = new_data['lp'] - lp

                        if new_data['win']:
                            result, change = 'WON', 'PROMOTED'
                            lp_gain = f'+{lp_gain}'
                        else:
                            result, change = 'LOST', 'DEMOTED'

                        embed_name = f'{name} JUST {result} A RANKED GAME'

                        if tier != new_data['tier'] or division != new_data['division']:
                            embed_value = f'{change} : {member.mention} is now {new_data["tier"]} {new_data["division"]}'
                        else:
                            embed_value = f'{lp_gain} IN {tier.upper()} {division} | {member.mention}'

                        embedVar.add_field(name=embed_name, value=embed_value, inline=False)

                        if not data:
                            await cursor.execute('INSERT INTO updated (summonerName, tier, division, LP, lastmatch, win) VALUES (?, ?, ?, ?, ?, ?)',
                                                (name, new_data['tier'], new_data['division'], new_data['lp'], newmatch_id, new_data['win'],))
                    
                    if new_games:
                        embedVar.set_footer(text="Ranked Watch updates every 15 minutes | LP change might not always be accurate")
                        await guild.get_channel(text_channel).send(embed=embedVar)

                await cursor.execute('UPDATE players SET tier = (SELECT updated.tier FROM updated WHERE updated.summonerName = summonerName) WHERE EXISTS (SELECT updated.tier FROM updated WHERE updated.summonerName = summonerName), division = (SELECT updated.division FROM updated WHERE updated.summonerName = summonerName) WHERE EXISTS (SELECT updated.division FROM updated WHERE updated.summonerName = summonerName), LP = (SELECT updated.LP FROM updated WHERE updated.summonerName = summonerName) WHERE EXISTS (SELECT updated.LP FROM updated WHERE updated.summonerName = summonerName), lastmatch = (SELECT updated.lastmatch FROM updated WHERE updated.summonerName = summonerName) WHERE EXISTS (SELECT updated.lastmatch FROM updated WHERE updated.summonerName = summonerName)')
                await db.commit()
                await cursor.execute('DELETE FROM updated')   
            await db.commit()
        print("Ranked Watch cycle done")  

    @nextcord.slash_command(name="rankedwatch")
    async def rankedwatch(self, interaction:Interaction):
        pass

    @rankedwatch.subcommand(name='add')
    async def add(self, interaction:Interaction, member:nextcord.Member, summonername:str):
        '''Add/update a user to the Ranked Watch list. Make sure the summoner name is exactly typed. Only NA supported'''
        async with aiosqlite.connect("./database/main.db") as db:
            async with db.cursor() as cursor:
                await cursor.execute('SELECT * FROM rankedwatch WHERE id = ? AND guildID = ?', (member.id, interaction.guild_id,))
                data = await cursor.fetchone()

                if data:
                    await cursor.execute('UPDATE rankedwatch SET summonerName = ? WHERE id = ? AND guildID = ?', (summonername, member.id, interaction.guild_id,))
                    await interaction.response.send_message(f"{member} successfully updated as {summonername}")
                    await cursor.execute('SELECT summonerName FROM players WHERE summonerName = ?', (summonername,))
                    data = await cursor.fetchone()
                    if not data:
                        summoner = cass.get_summoner(name=summonername, region="NA")
                        match_id = self.get_last_match(summoner).id
                        ranked_data = self.get_ranked_data(summoner)
                        await cursor.execute('INSERT INTO players (summonerName, tier , division , LP, lastmatch) VALUES (?, ?, ?, ?, ?)',
                        (ranked_data['name'], ranked_data['tier'], ranked_data['division'], ranked_data['lp'], match_id,))
                else:
                    await cursor.execute('INSERT INTO rankedwatch (id, guildID, summonerName) VALUES (?, ?, ?)', (member.id, interaction.guild_id, summonername,))
                    await cursor.execute('SELECT * from players WHERE summonerName = ?', (summonername,))
                    ranked_data = await cursor.fetchone()

                    if not ranked_data:
                        summoner = cass.get_summoner(name=summonername, region="NA")
                        match_id = self.get_last_match(summoner).id
                        ranked_data = self.get_ranked_data(summoner)
                        await cursor.execute('INSERT INTO players (summonerName, tier , division , LP, lastmatch) VALUES (?, ?, ?, ?, ?)',
                        (ranked_data['name'], ranked_data['tier'], ranked_data['division'], ranked_data['lp'], match_id,))

                    await interaction.response.send_message(f"{member.mention} successfully added to Ranked Watch list as **{summonername}**")
            await db.commit()

    @rankedwatch.subcommand()
    async def remove(self, interaction:Interaction):
        pass

    @remove.subcommand(name='watchlist')
    #@application_checks.has_permissions(move_members=True)
    async def watchlist(self, interaction:Interaction, member:nextcord.Member):
        '''Stops updates for and removes member from Ranked Watch list'''
        async with aiosqlite.connect("./database/main.db") as db:
            async with db.cursor() as cursor:
                await cursor.execute('SELECT * FROM rankedwatch WHERE id = ? AND guildID = ?', (member.id, interaction.guild_id,))
                data = await cursor.fetchone()
                
                if data:
                    await cursor.execute('DELETE FROM rankedwatch WHERE id = ? AND guildID = ?', (member.id, interaction.guild_id,))
                    await interaction.response.send_message(f"{member.mention} successfully removed from Ranked Watch")
                else:
                    await interaction.response.send_message(f"{member.mention} not found in Ranked Watch list")
                    
            await db.commit()

    @remove.subcommand(name='playerlist')
    #@application_checks.has_permissions(administrator=True)
    async def playerlist(self, interaction:Interaction, summonername:str):
        '''Removes a player from the Ranked Watch database. Cannot be done if player is still on the Ranked Watch list'''
        async with aiosqlite.connect("./database/main.db") as db:
            async with db.cursor() as cursor:
                await cursor.execute('SELECT * FROM rankedwatch WHERE summonerName = ?', (summonername,))
                data = await cursor.fetchone()
                if data:
                    await interaction.response.send_message(f"Removal failed. Player **{summonername}** is still on a server's Ranked Watch list!")
                else:
                    await cursor.execute('SELECT * FROM players WHERE summonerName = ?', (summonername,))
                    ranked_data = await cursor.fetchone()
                    if ranked_data:
                        await cursor.execute('DELETE FROM players WHERE summonerName = ?', (summonername,))
                        await interaction.response.send_message(f'Player **{summonername}** successfully removed from Ranked Watch database')
                        await db.commit()
                    else:
                        await interaction.response.send_message(f'Player **{summonername}** not found in database')

    @rankedwatch.subcommand()
    async def print(self, interaction:Interaction):
        pass

    @print.subcommand(name='watchlist')
    async def watchlist(self, interaction:Interaction):
        '''Returns list of players in the ranked watch list'''
        async with aiosqlite.connect("./database/main.db") as db:
            async with db.cursor() as cursor:
                await cursor.execute('SELECT ID, summonerName FROM rankedwatch WHERE guildID = ?', (interaction.guild_id,))
                data = await cursor.fetchall()
                if data:
                    ranked_list = ''
                    for entry in data:
                        summonername = entry[1]
                        await cursor.execute('SELECT tier, division FROM players WHERE summonerName = ?', (summonername,))
                        rank = await cursor.fetchone()
                        member = interaction.guild.get_member(entry[0])
                        ranked_list += f'{member.mention}: {summonername}, {rank[0]} {rank[1]}\n'
                    await interaction.response.send_message(ranked_list)
                else:
                    await interaction.response.send_message('Ranked Watch list currently empty')

    @print.subcommand(name='playerlist')
    async def playerlist(self, interaction:Interaction):
        '''Returns list of players in player database'''
        async with aiosqlite.connect('./database/main.db') as db:
            async with db.cursor() as cursor:
                await cursor.execute('SELECT summonerName, tier, division, LP FROM players')
                data = await cursor.fetchall()
                if data:
                    player_list = ''
                    for entry in data:
                        player_list += f'{entry[0]}: {entry[1]} {entry[2]} with {entry[3]} LP\n'
                    await interaction.response.send_message(player_list)
                else:
                    await interaction.response.send_message('Player database currently empty')

    @rankedwatch.subcommand(name='purge')
    @application_checks.has_permissions(administrator=True)
    async def purge(self, interaction:Interaction):
        '''Removes all members in the server from the Ranked Watch list'''
        async with aiosqlite.connect('./database/main.db') as db:
            async with db.cursor() as cursor:
                await cursor.execute('DELETE FROM rankedwatch WHERE guildID = ?', (interaction.guild_id,))
            await db.commit()
        await interaction.response.send_message('All members removed from Ranked Watch list')

    @rankedwatch.subcommand(name='change_channel')
    @application_checks.has_permissions(administrator=True)
    async def change_channel(self, interaction:Interaction, channel:GuildChannel=SlashOption(channel_types=[ChannelType.text])):
        '''Change where Ranked Watch sends results messages to given text channel'''
        channel_id = channel.id
        async with aiosqlite.connect('./database/main.db') as db:
            async with db.cursor() as cursor:
                await cursor.execute('UPDATE servers SET rankedwatch_channel = ? WHERE guildID = ?', (channel_id, interaction.guild_id,))
            await db.commit()
        await interaction.response.send_message(f'Ranked Watch will now send messages to {interaction.guild.get_channel(channel_id).mention}')
        
def setup(bot):
    bot.add_cog(RankedWatch(bot))