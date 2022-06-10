from hashlib import new
from nextcord import Interaction
from nextcord.ext import commands, tasks
import nextcord
import aiosqlite
from bot import testingServerID, client
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
        self.rankedwatch.start()

    #@commands.Cog.listener()
    #async def rankedwatch(self):
    
    def get_last_match(self, summoner:cass.Summoner)->cass.Match:
        match_history = cass.get_match_history(
            continent=summoner.region.continent,
            puuid=summoner.puuid,
            queue=cass.Queue.ranked_solo_fives,
        )
        return match_history[0]

    def get_ranked_data(self, summoner:cass.Summoner):
        target = [entry for entry in summoner.league_entries.fives.league.entries if entry.summoner.name == summoner.name][0]
        res = {
            'tier': str(target.tier),
            'division': str(target.division),
            'lp': target.league_points
        }
        return res

    #purely for testing
    @commands.command()
    async def randommatch(self, interaction:Interaction, summonername):
        newmatch = ''.join(random.choice(string.ascii_letters) for i in range(10))
        async with aiosqlite.connect("./database/main.db") as db:
            async with db.cursor() as cursor:
                await cursor.execute('UPDATE players SET lastmatch = ? WHERE summonerName = ?', (newmatch, summonername,))
            await db.commit()
        await interaction.send('Done')

    @tasks.loop(minutes=15)
    async def rankedwatch(self):
        async with aiosqlite.connect("./database/main.db") as db:
            async with db.cursor() as cursor:

                await cursor.execute('SELECT guildID FROM servers')
                guilds = await cursor.fetchall()

                for guild_entry in guilds:
                    guild_id = guild_entry[0]
                    guild = self.bot.get_guild(guild_id)

                    embedVar = nextcord.Embed(title="Ranked Watch Results", color=0x4eceef)
                    new_games = False

                    await cursor.execute('SELECT players.*, rankedwatch.id FROM players INNER JOIN rankedwatch ON rankedwatch.summonerName=players.summonerName')
                    players = await cursor.fetchall()
                    
                    for player in players:
                        name = player[0]
                        tier = player[1]
                        division = player[2]
                        lp = player[3]
                        lastmatch_id = player[4]
                        #member = guild.get_member(player[5])

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
                                'lp': data[3],
                                'win': True if data[5] else False
                            }
                        else:
                            newmatch = self.get_last_match(summoner)
                            newmatch_id = newmatch.id
                            if newmatch_id == lastmatch_id:
                                continue
                            new_data = self.get_ranked_data(summoner)
                            new_data['win'] = newmatch.participants[summoner.name].stats.win

                        new_games = True
                        result = change = ''
                        lp_gain = new_data['lp'] - lp

                        if new_data['win']:
                            result, change = 'WON', 'PROMOTED'
                        else:
                            result, change = 'LOST', 'DEMOTED'

                        embed_name = f'{name} JUST {result} A RANKED GAME'
                        embed_value = f'{lp_gain} IN {tier.upper()} {division}'

                        if tier != new_data['tier'] or division != new_data['division']:
                            embed_value += f' --> {change} : {new_data["tier"]} {new_data["division"]}'

                        embedVar.add_field(name=embed_name, value=embed_value, inline=False)

                        if not data:
                            await cursor.execute('INSERT INTO updated (summonerName, tier, division, LP, lastmatch, win) VALUES (?, ?, ?, ?, ?, ?)',
                                                (name, new_data['tier'], new_data['division'], new_data['lp'], newmatch_id, new_data['win'],))
                    
                    if new_games:
                        embedVar.set_footer(text="Ranked Watch updates every 15 minutes")
                        await guild.text_channels[0].send(embed=embedVar)

                await cursor.execute('UPDATE players SET (tier, division, LP, lastmatch) = (updated.tier, updated.division, updated.LP, updated.lastmatch) \
                                    FROM updated WHERE updated.summonerName = players.summonerName')
                await db.commit()
                await cursor.execute('DELETE FROM updated')   
            await db.commit()  

    @client.slash_command(guild_ids=[testingServerID])
    async def addtowatch(self, interaction:Interaction, member:nextcord.Member, summonername:str):
        '''Add/update a user to the Ranked Watch list. Make sure the summoner name is exactly typed. Only NA supported'''
        async with aiosqlite.connect("./database/main.db") as db:
            async with db.cursor() as cursor:
                await cursor.execute('SELECT * FROM rankedwatch WHERE id = ? AND guildID = ?', (member.id, interaction.guild_id,))
                data = await cursor.fetchone()
                if data:
                    await cursor.execute('UPDATE rankedwatch SET summonerName = ? WHERE id = ? AND guildID = ?', (summonername, member.id, interaction.guild_id,))
                    await interaction.response.send_message(f"{member} successfully updated as {summonername}")
                else:
                    await cursor.execute('INSERT INTO rankedwatch (id, guildID, summonerName) VALUES (?, ?, ?)', (member.id, interaction.guild_id, summonername,))

                    await cursor.execute('SELECT * from players WHERE summonerName = ?', (summonername,))
                    ranked_data = await cursor.fetchone()
                    if not ranked_data:

                        summoner = cass.get_summoner(name=summonername, region="NA")
                        match_id = self.get_last_match(summoner).id
                        ranked_data = self.get_ranked_data(summoner)

                        await cursor.execute('INSERT INTO players (summonerName, tier , division , LP, lastmatch) VALUES (?, ?, ?, ?, ?)',
                        (ranked_data['name'], ranked_data['tier'], ranked_data['div'], ranked_data['lp'], match_id,))

                    await interaction.response.send_message(f"{member.mention} successfully added to Ranked Watch list as **{summonername}**")
            await db.commit()

    @client.slash_command(guild_ids=[testingServerID])
    async def removefromwatch(self, interaction:Interaction, member:nextcord.Member):
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

    @client.slash_command(guild_ids=[testingServerID])
    async def removefromranked(self, interaction:Interaction, summonername:str):
        '''Removes a player from the Ranked Watch database. Cannot be done if player is still on the Ranked Watch list'''
        async with aiosqlite.connect("./database/main.db") as db:
            async with db.cursor() as cursor:
                await cursor.execute('SELECT * FROM rankedwatch WHERE guildID = ? AND summonerName = ?', (interaction.guild_id, summonername,))
                data = await cursor.fetchone()
                if data:
                    await interaction.response.send_message(f'Removal failed. Player **{summonername}** is still on the Ranked Watch list!')
                else:
                    await cursor.execute('SELECT * FROM players WHERE summonerName = ?', (summonername,))
                    ranked_data = await cursor.fetchone()
                    if ranked_data:
                        await cursor.execute('DELETE FROM players WHERE summonerName = ?', (summonername,))
                        await interaction.response.send_message(f'Player **{summonername}** successfully removed from Ranked Watch database')
                        await db.commit()
                    else:
                        await interaction.response.send_message(f'Player **{summonername}** not found in database')

def setup(bot):
    bot.add_cog(RankedWatch(bot))