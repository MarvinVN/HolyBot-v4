from datapipelines import NotFoundError
from nextcord import Interaction, SlashOption, ChannelType
from nextcord.abc import GuildChannel
from nextcord.ext import commands, tasks, application_checks
from dotenv import load_dotenv
from bot import db_servers, db_rankedwatch, db_player_cache
import nextcord
import cassiopeia as cass
import os

load_dotenv()
API_KEY = os.getenv("RIOT_API_KEY")
cass.set_riot_api_key(API_KEY)

regions = {'BR', 'EUNE', 'EUW', 'JP', 'KR', 'LAN', 'LAS', 'NA', 'OCE', 'TR', 'RU'}

class RankedWatch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.rankedwatch_loop.start()

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

                '''
                Current Bug in cassiopeia library, RANKED_TFT_DOUBLE_UP ranks are showing up with regular league ranks and cassiopeia doesn't know what to do with it.
                No real fix right now besides waiting for cassiopeia to update and just not have any ranked double up players on the ranked watch list.
                '''

                print(e.args[0])
            else:
                raise e
        return res

    @tasks.loop(minutes=15)
    async def rankedwatch_loop(self):
        servers = await db_rankedwatch.get_all()
        for server in servers:
            server_id = server.pop('_id')
            members = server
            
            guild = self.bot.get_guild(server_id)
            if guild is None: continue

            text_channel_id = await db_servers.find(server_id)
            text_channel = guild.get_channel(text_channel_id['rw_channel'])
            
            embedVar = nextcord.Embed(title="Ranked Watch Results", color=0x4eceef)
            embedVar.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/LoL_icon.svg/256px-LoL_icon.svg.png?20201029024159")
            new_games = False
            for member_id in members:
                member_data = members[member_id]
                summonername = member_data['summonerName']
                region = member_data['region']
                puuid = member_data['puuid']
                tier = member_data['tier']
                division = member_data['division']
                lp = member_data['lp']
                lastmatch_id = member_data['lastmatch_id']

                ranked_data = {}
                embed_name = embed_value = newmatch_id = ''
                member = guild.get_member(int(member_id))
                summoner = cass.get_summoner(name=summonername, region=region)

                cached = await db_player_cache.find(puuid)
                if cached:
                    cached.pop('_id')
                    ranked_data = cached
                    newmatch_id = ranked_data['newmatch_id']
                else:
                    newmatch = self.get_last_match(summoner)
                    newmatch_id = str(newmatch.id)

                    '''
                    This is needed due to the match_id sometimes returning without the region tag.
                    A quick fix, shouldn't affect other regions since everything will have NA1_ in front of it
                    '''
                    if newmatch_id[:4] != "NA1_":
                            newmatch_id = "NA1_" + newmatch_id


                    if newmatch_id == lastmatch_id:
                        continue

                    ranked_data = self.get_ranked_data(summoner)
                    ranked_data['win'] = newmatch.participants[summoner.name].stats.win

                new_games = True
                result = rank_change = ''
                lp_gain = ranked_data['lp'] - lp

                if ranked_data['win']:
                    result, rank_change = 'WON', 'PROMOTED'
                else:
                    result, rank_change = 'LOST', 'DEMOTED'

                embed_name = f'{summonername} JUST {result} A RANKED GAME'
                
                if tier != ranked_data['tier'] or division != ranked_data['division']:
                    embed_value = f'{rank_change} : {member.mention} is now {ranked_data["tier"]} {ranked_data["division"]}'
                else:
                    embed_value = f'{lp_gain:+} IN {tier.upper()} {division} | {member.mention}'

                embedVar.add_field(name=embed_name, value=embed_value, inline=False)

                if not cached:
                    await db_player_cache.insert({'_id': puuid, 'tier': ranked_data['tier'], 'division': ranked_data['division'], 'lp': ranked_data['lp'], 'win': ranked_data['win'], 'newmatch_id': newmatch_id})

                await db_rankedwatch.update({"_id": server_id, member_id:{'summonerName': summonername, 'region': region, 'puuid': puuid, 'tier': ranked_data['tier'], 'division': ranked_data['division'], 'lp': ranked_data['lp'], 'lastmatch_id': newmatch_id}})

            if new_games:
                embedVar.set_footer(text="Ranked Watch updates every 15 minutes | LP change might not always be accurate")
                await text_channel.send(embed=embedVar)
        
        players = await db_player_cache.get_all()
        for player in players:
            await db_player_cache.delete(player['_id'])
                
        print("Ranked Watch cycle done")  

    @nextcord.slash_command(name="rankedwatch")
    async def rankedwatch(self, interaction:Interaction):
        pass

    @rankedwatch.subcommand(name='add')
    async def add(self, interaction:Interaction, member:nextcord.Member=SlashOption(description="Server member to keep track of."),
                        summonername:str=SlashOption(description="Account to keep track of. Make sure summoner name is exactly typed"),
                        region:str=SlashOption(choices=regions, description="Region the account plays in.")):
        '''Add/update a user to the Ranked Watch list.'''
        if region not in regions:
            await interaction.response.send_message("Invalid region. Valid regions are: " + ', '.join(regions))
            return
        
        try:
            summoner = cass.get_summoner(name=summonername, region=region)
        except NotFoundError:
            await interaction.response.send_message("Summoner not found")
            return

        match_id = self.get_last_match(summoner).id
        ranked_data = self.get_ranked_data(summoner)
        data = {'summonerName': summonername, 
                'region': region, 
                'puuid': summoner.puuid, 
                'tier': ranked_data['tier'], 
                'division': ranked_data['division'], 
                'lp': ranked_data['lp'], 
                'lastmatch_id': match_id}

        await db_rankedwatch.upsert({'_id': interaction.guild_id, str(member.id): data})
        await interaction.response.send_message(f"{member.mention} successfully added to Ranked Watch list as **{summonername}**")

    @rankedwatch.subcommand()
    #@application_checks.has_permissions(move_members=True)
    async def remove(self, interaction:Interaction, member:nextcord.Member=SlashOption(description="Member to remove from Ranked Watch")):
        '''Stops updates for and removes member from Ranked Watch list'''
        try:
            await db_rankedwatch.unset({"_id": interaction.guild_id, str(member.id): ''})
            await interaction.response.send_message("Successfully removed from Ranked Watch")
        except KeyError:
            await interaction.response.send_message(f"{member.mention} not found in Ranked Watch list")

    @rankedwatch.subcommand()
    async def print(self, interaction:Interaction):
        '''Returns list of players in the ranked watch list'''
        entries = await db_rankedwatch.find(interaction.guild_id)
        entries.pop('_id')
        if entries:
            ranked_list = ''
            for member_id in entries:
                ranked_info = entries[member_id]
                member = interaction.guild.get_member(int(member_id))
                summonername = ranked_info['summonerName']
                tier = ranked_info['tier']
                division = ranked_info['division']
                lp = ranked_info['lp']
                
                ranked_list += f'{member.mention}: {summonername}, {tier} {division} {lp} LP\n'
            await interaction.response.send_message(ranked_list)
        else:
            await interaction.response.send_message('Ranked Watch list currently empty')

    @rankedwatch.subcommand(name='purge')
    @application_checks.has_permissions(administrator=True)
    async def purge(self, interaction:Interaction):
        '''Remove entire server from Ranked Watch'''
        await db_rankedwatch.replace_one({"_id": interaction.guild_id}, {"_id": interaction.guild_id})
        await interaction.response.send_autocomplete("Server Ranked Watch purged")

    # needs testing
    @rankedwatch.subcommand(name='change_channel')
    @application_checks.has_permissions(administrator=True)
    async def change_channel(self, interaction:Interaction, channel:GuildChannel=SlashOption(channel_types=[ChannelType.text], description="Channel to send Ranked Watch updates to.")):
        '''Change where Ranked Watch sends results messages to given text channel'''
        await db_servers.update({"_id": interaction.guild_id, "rw_channel": channel.id})
        await interaction.response.send_message(f'Ranked Watch updates will now be sent to {interaction.guild.get_channel(channel.id).mention}')
        
def setup(bot):
    bot.add_cog(RankedWatch(bot))