from nextcord import Guild

def get_first_valid_text_channel_id(guild:Guild):
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            text_channel = channel.id
            return text_channel