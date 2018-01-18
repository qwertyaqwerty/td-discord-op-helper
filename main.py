import discord
import asyncio
import json
import functools
import requests

CONFIG_FILE_PATH = 'config.json'
CHECKPOINT_FILE_PATH = 'checkpoint.json'

client = discord.Client()

class OpsDatas:
    def __init__(self):
        self.channels = []
        self.channel_parent_id = None
        self.restricted_channel = None
        self.log_recieved_messages = False
        self.minion_bot_channel = None
        self.attack_log_offset = None
        self.clan_tag = None
        self.background_refresh_task = None

global g_ops_datas
g_ops_datas = OpsDatas()

global wm_bot_id
wm_bot_id = None

global minion_bot_id
minion_bot_id = None

global refresh_interval
refresh_interval = None

global coc_api_token
coc_api_token = None

async def handle_new_attack(attack):
    pass

async def check_message(message):
    if message.author.id == client.user.id:
        return False

    if message.content.startswith('!channel_info'):
        return True

    if g_ops_datas.restricted_channel is None:
        if message.content.startswith('!restrict_channel'):
            return True
        else:
            await client.send_message(message.channel, "channel not restricted. Restrict with `!restrict_channel`")
            return False

    if g_ops_datas.log_recieved_messages:
        await client.send_message(g_ops_datas.restricted_channel, 
            'recieved message from channel id: `{}` `{}`, user id:`{}` name:`{}`:\n```\n{}\n```\nembeds: {}\nattachments:{}\n'.format(
                message.channel.id, message.channel.name, message.author.id, message.author.name, message.content, message.embeds,
                message.attachments))

    if message.author.id == wm_bot_id:
        return True

    if message.author.id == minion_bot_id:
        if g_ops_datas.minion_bot_channel is not None and message.channel.id == g_ops_datas.minion_bot_channel.id:
            return True
        else:
            return False

    return g_ops_datas.restricted_channel.id == message.channel.id

async def handle_wm_message(message):
    pass
    # await client.send_message(g_ops_datas.restricted_channel, 'recieved message from wmbot:\n```\n{}\n```'.format(message.content))

async def handle_mb_message(message):
    # await client.send_message(g_ops_datas.restricted_channel, 
        # 'recieved message from minion bot:\n```\n{}\n```\nembeds: {}\nattachments:{}\n'.format(message.content, message.embeds, message.attachments))
    print(message.content)

def fetch_current_war():
    print('fetching from api...')
    url = 'https://api.clashofclans.com/v1/clans/%23{}/currentwar'.format(g_ops_datas.clan_tag)
    r = requests.get(url, headers={'Accept': 'application/json', 'authorization': 'Bearer {}'.format(coc_api_token)})
    r.raise_for_status()
    response = r.json()
    return response

async def wait_task_list(task_list):
    await asyncio.gather(*task_list)

async def handle_new_attack(attack, players):
    attacker = players[attack['attackerTag']]
    defender = players[attack['defenderTag']]
    message_content = '{}. th{} {} attacks {}. th{} {} for {} %{}'.format(
        attacker['mapPosition'], attacker['townhallLevel'], attacker['name'],
        defender['mapPosition'], defender['townhallLevel'], defender['name'],
        ':star:' * attack['stars'], attack['destructionPercentage'])
    await client.send_message(g_ops_datas.restricted_channel, message_content)

async def handle_new_defense(attack, players):
    attacker = players[attack['attackerTag']]
    defender = players[attack['defenderTag']]
    message_content = '{}. th{} {} defends {}. th{} {} for {} %{}'.format(
        defender['mapPosition'], defender['townhallLevel'], defender['name'],
        attacker['mapPosition'], attacker['townhallLevel'], attacker['name'],
        ':star:' * attack['stars'], attack['destructionPercentage'])
    await client.send_message(g_ops_datas.restricted_channel, message_content)

async def refresh_war_channel(player):
    if player['side'] != 'opponent':
        return

    print('refreshing channel for player...')
    print(json.dumps(player, indent=4))

    stars = player['bestOpponentAttack']['stars']
    cleared = stars == 3 or (player['townhallLevel'] == 11 and stars >= 2)
    defs = player['opponentAttacks']
    if defs == 0:
        status = ''
    elif cleared:
        status = '-cleared'
    else:
        status = '-0/{}'.format(defs)
    pos = player['mapPosition']

    new_name = '{}-th{}{}'.format(pos, player['townhallLevel'], status)
    await client.send_message(g_ops_datas.restricted_channel, 'Changing channel {} to {}'.format(g_ops_datas.channels[pos-1].name, name))

    global g_ops_datas
    await client.edit_channel(g_ops_datas.channels[pos - 1], name=new_name)

async def refresh_current_war():
    global g_ops_datas

    response = fetch_current_war()

    if response["state"] != "inWar":
        g_ops_datas.attack_log_offset = None
        return

    tag_2_player = {}
    for side in ['clan', 'opponent']:
        for member in response[side]['members']:
            member['side'] = side
            member['needRefresh'] = False
            tag_2_player[member['tag']] = member

    if g_ops_datas.attack_log_offset is None:
        g_ops_datas.attack_log_offset = 0

    async_tasks = []

    new_offset = g_ops_datas.attack_log_offset
    for member in response['clan']['members']:
        if "attacks" not in member:
            continue
        for attack in member['attacks']:
            if attack['order'] > g_ops_datas.attack_log_offset:
                async_tasks.append(handle_new_attack(attack, tag_2_player))
                tag_2_player[attack['defenderTag']]['needRefresh'] = True
                if new_offset < attack['order']:
                    new_offset = attack['order']

    for member in response['opponent']['members']:
        if "attacks" not in member:
            continue
        for attack in member['attacks']:
            if attack['order'] > g_ops_datas.attack_log_offset:
                async_tasks.append(handle_new_defense(attack, tag_2_player))
                tag_2_player[attack['defenderTag']]['needRefresh'] = True
                if new_offset < attack['order']:
                    new_offset = attack['order']

    g_ops_datas.attack_log_offset = new_offset
    print('update data complete, new_offset = {}'.format(new_offset))

    for tag in tag_2_player:
        player = tag_2_player[tag]
        if player['needRefresh']:
            print('player need refresh: ')
            print(json.dumps(player, indent=4))
            async_tasks.append(refresh_war_channel(player))

    await wait_task_list(async_tasks)

async def periodic_task(interval, task):
    await asyncio.sleep(interval)
    await task
    global g_ops_datas
    g_ops_datas.background_refresh_task = asyncio.ensure_future(periodic_task(interval, task))

@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')

    print('loading checkpoint...')
    try:
        load_checkpoint(CHECKPOINT_FILE_PATH)
        print('checkpoint loaded!')
    except:
        print('checkpoint not exist.')

    if g_ops_datas.clan_tag is not None:
        print('set up refresh...')
        g_ops_datas.background_refresh_task = asyncio.ensure_future(periodic_task(refresh_interval, refresh_current_war()))

@client.event
async def on_message(message):
    if not await check_message(message):
        return

    if message.author.id == wm_bot_id:
        await handle_wm_message(message)
        return

    if message.author.id == minion_bot_id:
        await handle_mb_message(message)
        return

    if message.content.startswith('!create_channels'):
        if g_ops_datas.channel_parent_id is None:
            await client.send_message(message.channel, 'parent_id not set!')
            return
        args = message.content.split(' ')[1:]
        global g_ops_datas
        async_tasks = []
        idx = 0
        for i, arg in enumerate(args):
            th = 11 - i
            num = int(arg)
            for j in range(0, num):
                idx += 1
                async_tasks.append(client.create_channel(message.server, "{}-th{}".format(idx, th), parent_id=g_ops_datas.channel_parent_id))
        for async_task in async_tasks:
            g_ops_datas.channels.append(await async_task)
        await client.send_message(message.channel, "{} channels created!".format(idx))
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
        if g_ops_datas.channel_parent_id is None:
            await client.send_message(message.channel, 'parent_id not set!')
            return
        async_tasks = []
        for channel in message.server.channels:
            if channel != message.channel and channel.parent_id == g_ops_datas.channel_parent_id:
                async_tasks.append(client.delete_channel(channel))
        for async_task in async_tasks:
            await async_task
        await client.send_message(message.channel, 'channels deleted!')
    elif message.content.startswith('!send_war_messages'):
        if g_ops_datas.channel_parent_id is None:
            await client.send_message(message.channel, 'parent_id not set!')
            return
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
        if g_ops_datas.channel_parent_id is None:
            await client.send_message(message.channel, 'parent_id not set!')
            return
        prefix_len = len('!send_category_messages')
        message_content = message.content[prefix_len+1:]
        async_tasks = []
        for channel in message.server.channels:
            if channel.parent_id == g_ops_datas.channel_parent_id:
                async_tasks.append(client.send_message(channel, message_content))
        for async_task in async_tasks:
            await async_task
        await client.send_message(message.channel, 'messages sent to category!')
    elif message.content.startswith('!get_parent_id'):
        if g_ops_datas.channel_parent_id is None:
            await client.send_message(message.channel, 'parent_id not set. set with `!set_category`')
        else:
            await client.send_message(message.channel, 'parent_id is `{}`'.format(g_ops_datas.channel_parent_id))
    elif message.content.startswith('!get_channels'):
        if len(g_ops_datas.channels) == 0:
            await client.send_message(message.channel, 'none found!')
        else:
            single_fmt = '{}. id: `{}` name: `{}`'
            lines = []
            for i, channel in enumerate(g_ops_datas.channels):
                lines.append(single_fmt.format(i, channel.id, channel.name))
            message_content = '\n'.join(lines)
            await client.send_message(message.channel, message_content)
    elif message.content.startswith('!restrict_channel'):
        global g_ops_datas
        g_ops_datas.restricted_channel = message.channel
        await client.send_message(message.channel, 'channel restricted to `{}`: `{}`'.format(message.channel.id, message.channel.name))
    elif message.content.startswith('!ping'):
        await client.send_message(message.channel, 'pong!')
    elif message.content.startswith('!toggle_log_recieved_messages'):
        global g_ops_datas
        g_ops_datas.log_recieved_messages = not g_ops_datas.log_recieved_messages
        await client.send_message(message.channel, 'log recieved messages set to {}'.format(g_ops_datas.log_recieved_messages))
    elif message.content.startswith('!set_mb_channel'):
        channel_id = message.content.split(' ')[1]
        global g_ops_datas
        g_ops_datas.minion_bot_channel = client.get_channel(channel_id)
        await client.send_message(message.channel, 'minion bot interaction channel set to `{}`: `{}`'.format(
            g_ops_datas.minion_bot_channel.id, g_ops_datas.minion_bot_channel.name))
    elif message.content.startswith('!get_mb_channel'):
        if g_ops_datas.minion_bot_channel is None:
            await client.send_message(message.channel, 'mb_channel not set!')
            return
        await client.send_message(message.channel, 'minion bot interaction channel is `{}`: `{}`'.format(
            g_ops_datas.minion_bot_channel.id, g_ops_datas.minion_bot_channel.name))
    elif message.content.startswith('!set_clan_tag'):
        global g_ops_datas
        clan_tag = message.content.split(' ')[1]
        g_ops_datas.clan_tag = clan_tag
        g_ops_datas.attack_log_offset = None
        if g_ops_datas.background_refresh_task is None:
            g_ops_datas.background_refresh_task = asyncio.ensure_future(periodic_task(refresh_interval, refresh_current_war()))
        await client.send_message(message.channel, 'clan tag set to {}'.format(clan_tag))
    else:
        await client.send_message(message.channel, 'Prefix not recognized.')


def load_checkpoint(checkpoint_file_path):
    with open(checkpoint_file_path, 'r') as f:
        config = json.loads(f.read())

    global g_ops_datas
    if "channel_parent_id" in config:
        g_ops_datas.channel_parent_id = config["channel_parent_id"]
    if "channels" in config:
        g_ops_datas.channels = []
        for channel_id in config["channels"]:
            g_ops_datas.channels.append(client.get_channel(channel_id))
    if "restricted_channel" in config:
        g_ops_datas.restricted_channel = client.get_channel(config["restricted_channel"])
    if "minion_bot_channel" in config:
        g_ops_datas.minion_bot_channel = client.get_channel(config["minion_bot_channel"])
    if "attack_log_offset" in config:
        g_ops_datas.attack_log_offset = config["attack_log_offset"]
    if "clan_tag" in config:
        g_ops_datas.clan_tag = config["clan_tag"]

def save_checkpoint(checkpoint_file_path):
    config = {}
    if g_ops_datas.channel_parent_id is not None:
        config["channel_parent_id"] = g_ops_datas.channel_parent_id
    config["channels"] = []
    for channel in g_ops_datas.channels:
        config["channels"].append(channel.id)
    if g_ops_datas.restricted_channel is not None:
        config["restricted_channel"] = g_ops_datas.restricted_channel.id
    if g_ops_datas.minion_bot_channel is not None:
        config["minion_bot_channel"] = g_ops_datas.minion_bot_channel.id
    if g_ops_datas.attack_log_offset is not None:
        config["attack_log_offset"] = g_ops_datas.attack_log_offset
    if g_ops_datas.clan_tag is not None:
        config["clan_tag"] = g_ops_datas.clan_tag

    with open(checkpoint_file_path, 'w') as f:
        f.write(json.dumps(config, indent=4))

def main():
    with open(CONFIG_FILE_PATH, 'r') as f:
        config = json.loads(f.read())
        bot_token = config["bot_token"]
        global wm_bot_id
        if "wm_bot_id" in config:
            wm_bot_id = config["wm_bot_id"]
        global minion_bot_id
        if "minion_bot_id" in config:
            minion_bot_id = config["minion_bot_id"]
        global refresh_interval
        refresh_interval = config["refresh_interval"]
        global coc_api_token
        coc_api_token = config["coc_api_token"]

    client.run(bot_token)

    save_checkpoint(CHECKPOINT_FILE_PATH)

main()
