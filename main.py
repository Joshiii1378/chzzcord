import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord.ui import Button, View
from datetime import timedelta
import requests
import json
import re
import subprocess

load_dotenv()  # .env 파일에서 환경 변수 로드

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
}

def search_channel(keyword):
    url = f'https://api.chzzk.naver.com/service/v1/search/channels?keyword={keyword}'
    try:
        response = requests.get(url, headers=headers)
        return response.json().get('content', {}).get('data', [])
    except Exception as e:
        print(f"Error fetching chat channel data: {e}")
        return None

def get_channel_name(channel_id):
    url = f'https://api.chzzk.naver.com/service/v2/channels/{channel_id}/live-detail'
    try:
        response = requests.get(url, headers=headers)
        return response.json().get('content', {}).get('channel').get('channelName')
    except Exception as e:
        print(f"Error fetching chat channel data: {e}")
        return None

class AlertView(View):
    def __init__(self, name):
        super().__init__(timeout=60)
        self.name = name
        self.broadcast_button = Button(label=f"{name} 방송 알림", style=discord.ButtonStyle.primary, custom_id=f"{name}-방송-알림")
        self.chat_button = Button(label=f"{name} 채팅 알림", style=discord.ButtonStyle.primary, custom_id=f"{name}-채팅-알림")
        self.add_item(self.broadcast_button)
        self.add_item(self.chat_button)
        self.broadcast_button.callback = self.broadcast_callback
        self.chat_button.callback = self.chat_callback

    async def broadcast_callback(self, interaction: discord.Interaction):
        custom_id = interaction.data['custom_id']
        channel_name = custom_id
        guild = interaction.guild
        existing_channel = discord.utils.get(guild.channels, name=channel_name)
        if not existing_channel:
            new_channel = await guild.create_text_channel(channel_name)
        else:
            new_channel = existing_channel

        webhooks = await new_channel.webhooks()
        if not webhooks:
            webhook = await new_channel.create_webhook(name=channel_name)
        else:
            webhook = webhooks[0]

        webhook_url = webhook.url
        print(f"Webhook URL for {channel_name}: {webhook_url}")

        for item in self.children:
            if item.custom_id == custom_id:
                item.disabled = True
                break

        await interaction.response.edit_message(view=self)

        '''
        with open(f'{self.name}_webhook_url.txt', 'w') as f:
            f.write(webhook_url)
        '''

        streamer_id = streamer[self.name]
        subprocess.Popen(['python3', 'message.py', webhook_url, streamer_id])

    async def chat_callback(self, interaction: discord.Interaction):
        custom_id = interaction.data['custom_id']
        channel_name = custom_id
        guild = interaction.guild
        existing_channel = discord.utils.get(guild.channels, name=channel_name)
        if not existing_channel:
            new_channel = await guild.create_text_channel(channel_name)
        else:
            new_channel = existing_channel

        webhooks = await new_channel.webhooks()
        if not webhooks:
            webhook = await new_channel.create_webhook(name=channel_name)
        else:
            webhook = webhooks[0]

        webhook_url = webhook.url
        print(f"Webhook URL for {channel_name}: {webhook_url}")

        for item in self.children:
            if item.custom_id == custom_id:
                item.disabled = True
                break

        await interaction.response.edit_message(view=self)

        '''
        with open(f'{self.name}_webhook_url.txt', 'w') as f:
            f.write(webhook_url)
        '''
        streamer_id = streamer[self.name]
        subprocess.Popen(['python3', 'croller.py', streamer_id, webhook_url])

def choice_channel_id(channels, index):
    if 1 <= index <= len(channels):
        return channels[index - 1]["channel"]["channelId"]
    else:
        return None

def choice_channel_name(channels, index):
    if 1 <= index <= len(channels):
        return channels[index - 1]["channel"]["channelName"]
    else:
        return None

file_path = 'data.JSON'
streamer = {}

@bot.command()
async def 추가(ctx, *, keyword):
    if re.fullmatch(r'[a-f0-9]{32}', keyword):
        channelName = get_channel_name(keyword)
        streamer[channelName] = keyword
        '''
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(streamer, f, ensure_ascii=False)
        '''
        description = f"{channelName}에 대한 알림을 설정하세요."
        embed = discord.Embed(title="알림 설정", description=description)
        view = AlertView(channelName)
        message = await ctx.send(embed=embed, view=view)
        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(minutes=1))
        await message.delete()
    else:
        channels = search_channel(keyword)
        if channels:
            searchList = ""
            for index, channel in enumerate(channels, start=1):
                channelName = channel["channel"]["channelName"]
                follower_count = channel["channel"]["followerCount"]
                searchList += f"{index}. {channelName}, 팔로우 수: {follower_count}\n"
            await ctx.send(searchList)
                
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel
            try:
                msg = await bot.wait_for('message', check=check, timeout=30)
                choice = int(msg.content)
                channelId = choice_channel_id(channels, choice)
                channelName = choice_channel_name(channels, choice)
                if channelId:
                    streamer[channelName] = channelId
                    '''
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(streamer, f, ensure_ascii=False)
                    '''
                    description = f"{channelName}에 대한 원하는 알림을 선택하세요."
                    embed = discord.Embed(title="알림 설정", description=description)
                    view = AlertView(channelName)
                    message = await ctx.send(embed=embed, view=view)
                    await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(minutes=1))
                    await message.delete()
                else:
                    await ctx.send("잘못된 채널 번호입니다.")
            except ValueError:
                await ctx.send("숫자를 입력해야 합니다.")
            except Exception as e:
                await ctx.send("입력 시간이 초과되었습니다.")
        else:
            await ctx.send("채널 정보를 가져오는 데 실패했습니다.")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')

bot.run(TOKEN)

