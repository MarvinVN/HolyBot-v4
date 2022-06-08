from nextcord import Interaction
from nextcord.ext import commands
import nextcord
import aiosqlite
from bot import testingServerID, client
import cassiopeia as cass
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("RIOT_API_KEY")
cass.set_riot_api_key(API_KEY)  # This overrides the value set in your configuration/settings.

class RankedWatch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        async with aiosqlite.connect('./database/players.db') as db:
            async with db.cursor() as cursor:
                await cursor.execute('CREATE TABLE IF NOT EXISTS ranked (summonerName VARCHAR(16), tier VARCHAR(12), division VARCHAR(3), LP INTEGER, lastmatch VARCHAR(255))')
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

                    async with aiosqlite.connect("./database/players.db") as ranked_db:
                        async with ranked_db.cursor() as ranked_cursor:
                            await ranked_cursor.execute('SELECT * from ranked WHERE summonerName = ?', (summonername,))
                            ranked_data = await ranked_cursor.fetchone()
                            if not ranked_data:

                                summoner = cass.get_summoner(name=summonername, region="NA")
                                match_history = cass.get_match_history(
                                    continent=summoner.region.continent,
                                    puuid=summoner.puuid,
                                    queue=cass.Queue.ranked_solo_fives,
                                )
                                match = match_history[0].id

                                romeo = [entry for entry in summoner.league_entries.fives.league.entries if entry.summoner.name == summoner.name][0]

                                name = romeo.summoner.name
                                tier = str(romeo.tier)
                                div = str(romeo.division)
                                lp = romeo.league_points

                                await ranked_cursor.execute('INSERT INTO ranked (summonerName, tier , division , LP, lastmatch) VALUES (?, ?, ?, ?, ?)',
                                (name, tier, div, lp, match,))
                        await ranked_db.commit()
                        await interaction.response.send_message(f"{member} successfully added to Ranked Watch list as {summonername}")
            await db.commit()

    @client.slash_command(guild_ids=[testingServerID])
    async def removefromwatch(self, interaction:Interaction, member:nextcord.Member):
        '''Stops updates and removes member from Ranked Watch list'''
        async with aiosqlite.connect("./database/main.db") as db:
            async with db.cursor() as cursor:
                await cursor.execute('SELECT * FROM rankedwatch WHERE id = ? AND guildID = ?', (member.id, interaction.guild_id,))
                data = await cursor.fetchone()
                if data:
                    await cursor.execute('DELETE FROM rankedwatch WHERE id = ? and guildID = ?', (member.id, interaction.guild_id,))
                    await interaction.response.send_message(f"{member} successfully removed from Ranked Watch")

def setup(bot):
    bot.add_cog(RankedWatch(bot))