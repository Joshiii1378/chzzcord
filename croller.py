import os
from dotenv import load_dotenv
import asyncio
import json
import requests
import websockets
import aiohttp
import re
import sys
import discord
from discord.ext import commands

# 필수로 사용해야 하는 헤더
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
}

emoji_dict = {}  # 이모지 대체 딕셔너리

load_dotenv()  # .env 파일에서 환경 변수 로드

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
webhook_url = None

async def send_to_webhook(message):
    async with aiohttp.ClientSession() as session:
        payload = {
            "content": message
        }
        async with session.post(webhook_url, json=payload) as response:
            if response.status == 204:
                print("Message sent successfully")
            else:
                print(f"Failed to send message: {response.status}")

def get_chat_channel_id(streamer):
    url = f'https://api.chzzk.naver.com/polling/v2/channels/{streamer}/live-status'
    try:
        response = requests.get(url, headers=headers)
        return response.json().get('content', {}).get('chatChannelId')
    except Exception as e:
        print(f"Error fetching chat channel ID: {e}")
        return None

def get_access_token(chat_channel_id):
    url = f'https://comm-api.game.naver.com/nng_main/v1/chats/access-token?channelId={chat_channel_id}&chatType=STREAMING'
    try:
        response = requests.get(url, headers=headers)
        return response.json().get('content', {}).get('accessToken')
    except Exception as e:
        print(f"Error fetching access token: {e}")
        return None

async def replace_emojis(msg, guild):
    pattern = re.compile(r'{:(.*?):}')
    matches = pattern.findall(msg)
    for match in matches:
        if match in emoji_dict:
            emoji = emoji_dict[match]
            emoji_code = await determine_emoji_code(emoji)
            msg = msg.replace(f'{{:{match}:}}', emoji_code)
        else:
            print(f"Emoji {match} not found in emoji_dict")
    return msg

async def determine_emoji_code(emoji):
    if emoji.animated:
        emoji_code = f'<a:{emoji.name}:{emoji.id}>'
    else:
        emoji_code = f'<:{emoji.name}:{emoji.id}>'
    return emoji_code

async def upload_emoji(guild, name, url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            emoji_bytes = await response.read()
            try:
                emoji = await guild.create_custom_emoji(name=name, image=emoji_bytes)
                return emoji
            except discord.HTTPException as e:
                print(f"Failed to upload emoji {name}: {e}")
                return None

async def on_message(message, guild):
    try:
        data = json.loads(message)
        if 'bdy' in data and isinstance(data['bdy'], list):
            for item in data['bdy']:
                profile = json.loads(item.get('profile', '{}'))
                user_id_hash = profile.get('userIdHash')
                if user_id_hash != streamer_id:
                    continue  # 스트리머가 아닌 사람의 메시지는 무시
                extras = json.loads(item.get('extras', '{}'))
                emojis = extras.get('emojis', {})
                for emoji_name, emoji_link in emojis.items():
                    if emoji_name not in emoji_dict:
                        emoji = await upload_emoji(guild, emoji_name, emoji_link)
                        if emoji:
                            emoji_dict[emoji_name] = emoji
                nickname = profile.get('nickname', 'Unknown')
                msg = item.get('msg', 'No message')
                replaced_msg = await replace_emojis(msg, guild)
                await send_to_webhook(f"{nickname} : {replaced_msg}")
        elif 'bdy' in data and isinstance(data['bdy'], dict):
            profile = json.loads(data['bdy'].get('profile', '{}'))
            user_id_hash = profile.get('userIdHash')
            if user_id_hash != streamer_id:
                return  # 스트리머가 아닌 사람의 메시지는 무시
            extras = json.loads(data['bdy'].get('extras', '{}'))
            emojis = extras.get('emojis', {})
            for emoji_name, emoji_link in emojis.items():
                if emoji_name not in emoji_dict:
                    emoji = await upload_emoji(guild, emoji_name, emoji_link)
                    if emoji:
                        emoji_dict[emoji_name] = emoji
            nickname = profile.get('nickname', 'Unknown')
            msg = data['bdy'].get('msg', 'No message')
            replaced_msg = await replace_emojis(msg, guild)
            await send_to_webhook(f"{nickname} : {replaced_msg}")
    except Exception as e:
        print(f"Error processing message: {e}")

async def on_connect(websocket, chat_channel_id, access_token, guild):
    print("웹소켓 연결됨.")
    message = {
        "ver": "2",
        "cmd": 100,
        "svcid": "game",
        "cid": chat_channel_id,
        "bdy": {
            "uid": None,
            "devType": 2001,
            "accTkn": access_token,
            "auth": "READ"
        },
        "tid": 1
    }
    await websocket.send(json.dumps(message))

async def ping_pong(websocket, chat_channel_id, streamer_id):
    while True:
        await websocket.send(json.dumps({"ver": "2", "cmd": 0}))
        await asyncio.sleep(20)
        print("웹소켓 연결중.")
        new_chat_channel_id = get_chat_channel_id(streamer_id)
        if chat_channel_id != new_chat_channel_id:
            chat_channel_id = new_chat_channel_id
            break
    await websocket.close()
    print("웹소켓 연결 종료")

async def connect(streamer_id, guild):
    while True:
        try:
            chat_channel_id = get_chat_channel_id(streamer_id)
            access_token = get_access_token(chat_channel_id)
            async with websockets.connect(f'wss://kr-ss3.chat.naver.com/chat?accessToken={access_token}') as websocket:
                await on_connect(websocket, chat_channel_id, access_token, guild)
                task1 = asyncio.create_task(ping_pong(websocket, chat_channel_id, streamer_id))
                async for message in websocket:
                    await on_message(message, guild)
                await task1
        except Exception as e:
            print(f"Error in connection: {e}")
        print("Reconnecting in 5 seconds...")
        await asyncio.sleep(5)  # 5초 후 재연결 시도

@bot.event
async def on_ready():
    global webhook_url
    global streamer_id
    streamer_id = sys.argv[1]
    webhook_url = sys.argv[2]
    guild = discord.utils.get(bot.guilds)
    asyncio.create_task(connect(streamer_id, guild))
    print(f'Logged in as {bot.user}!')

if __name__ == "__main__":
    streamer_id = sys.argv[1]
    webhook_url = sys.argv[2]
    bot.run(TOKEN)
