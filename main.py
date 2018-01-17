import discord
import asyncio
import json

CONFIG_FILE_PATH = 'config.json'

client = discord.Client()

class OpsDatas:
    def __init__(self):
        self.channels = []
        self.channel_parent_id = None

global g_ops_datas
g_ops_datas = OpsDatas()

@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')

@client.event
async def on_message(message):
    if message.content.startswith('!create_channels'):
        channel_num_start = int(message.content.split(' ')[1])
        channel_num_end = int(message.content.split(' ')[2])
        global g_ops_datas
        async_tasks = []
        for i in range(channel_num_start, channel_num_end + 1):
            async_tasks.append(client.create_channel(message.server, "{}-".format(i), parent_id=g_ops_datas.channel_parent_id))
        for async_task in async_tasks:
            g_ops_datas.channels.append(await async_task)
        await client.send_message(message.channel, "{} channels created!".format(channel_num_end - channel_num_start + 1))
    elif message.content.startswith('!channel_info'):
        message_content = 'Channel id: `{id}`, Channel position: `{pos}`, parent id: `{parent}`'
        await client.send_message(message.channel, message_content.format(
            id=message.channel.id, pos=message.channel.position, parent=message.channel.parent_id))
    elif message.content.startswith('!set_category'):
        global g_ops_datas
        parent_id = message.content.split(' ')[1]
        g_ops_datas.channel_parent_id = parent_id
        g_ops_datas.channels = []
        await client.send_message(message.channel, "parent_id set to `{}`!".format(parent_id))
    elif message.content.startswith('!delete_channels'):
        global g_ops_datas
        async_tasks = []
        for channel in g_ops_datas.channels:
            async_tasks.append(client.delete_channel(channel))
        for async_task in async_tasks:
            await async_task
        g_ops_datas.channels = []
        await client.send_message(message.channel, 'channels deleted!')
    elif message.content.startswith('!delete_all_channels'):
        async_tasks = []
        for channel in message.server.channels:
            if channel != message.channel and channel.parent_id == message.channel.parent_id:
                async_tasks.append(client.delete_channel(channel))
        for async_task in async_tasks:
            await async_task
        await client.send_message(message.channel, 'channels deleted!')
    elif message.content.startswith('!send_war_messages'):
        prefix_len = len('!send_war_messages')
        message_fmt = '=========War with {}========='
        clan_name = message.content[prefix_len+1:]
        async_tasks = []
        for channel in message.server.channels:
            if channel.parent_id == g_ops_datas.channel_parent_id:
                async_tasks.append(client.send_message(channel, message_fmt.format(clan_name)))
        for async_task in async_tasks:
            await async_task
        await client.send_message(message.channel, 'messages sent!')
    elif message.content.startswith('!send_category_messages'):
        prefix_len = len('!send_category_messages')
        message_content = message.content[prefix_len+1:]
        async_tasks = []
        for channel in message.server.channels:
            if channel.parent_id == g_ops_datas.channel_parent_id:
                async_tasks.append(client.send_message(channel, message_content))
        for async_task in async_tasks:
            await async_task
        await client.send_message(message.channel, 'messages sent to category!')

def main():
    with open(CONFIG_FILE_PATH, 'r') as f:
        config = json.loads(f.read())
        bot_token = config["bot_token"]

    client.run(bot_token)


main()
