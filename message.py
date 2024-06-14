import requests
import asyncio
import aiohttp
import json
import sys

# Webhook URL 및 네이버 채널 ID 설정
WEBHOOK_URL = sys.argv[1]
Chzzk_channel_id = sys.argv[2]  # 네이버 채널 ID

last_title = None  # 이전 방송 제목을 저장할 변수
is_live = None  # 방송 중임을 확인하는 변수

# API 엔드포인트 URL
Chzzk_api_url = f'https://api.chzzk.naver.com/service/v2/channels/{Chzzk_channel_id}/live-detail'

# 필수로 사용해야 하는 헤더
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
}

# Naver API에서 상태 확인 함수
def check_naver_status():
    response = requests.get(Chzzk_api_url, headers=headers)
    if response.status_code == 200:
        return response.json().get('content', {}).get('status')
    else:
        print(f'Error Status code: {response.status_code}\nResponse: {response.text}')
        return None

# 임베드 메시지를 웹훅으로 전송하는 함수
async def send_embed_to_webhook(embed):
    async with aiohttp.ClientSession() as session:
        payload = {
            "embeds": [embed]
        }
        async with session.post(WEBHOOK_URL, json=payload) as response:
            if response.status == 204:
                print("Embed message sent successfully")
            else:
                print(f"Failed to send embed message: {response.status}")

# 주기적으로 Naver API 호출하여 상태 확인 및 웹훅에 메시지 전송
async def check_and_post_periodically():
    global last_title  # 전역 변수 사용 선언
    global is_live

    while True:
        naver_status = check_naver_status()
        print(naver_status)

        if naver_status == 'OPEN':
            response = requests.get(Chzzk_api_url, headers=headers)
            title = response.json().get('content', {}).get('liveTitle')
            channel = response.json().get('content', {}).get('channel').get('channelName')
            channelImageUrl = response.json().get('content', {}).get('channel').get('channelImageUrl')
            liveImageUrl = response.json().get('content', {}).get('liveImageUrl')
            liveImageUrl = liveImageUrl.replace('{type}', '1080')

            embed = {
                "description": f'## [{channel}님의 방송 시작!!](https://chzzk.naver.com/live/{Chzzk_channel_id})',
                "color": 0x62c1cc,
                "fields": [
                    {
                        "name": "방송 제목",
                        "value": '▶ ' + title,
                        "inline": True
                    }
                ],
                "author": {
                    "name": channel,
                    "icon_url": channelImageUrl
                },
                "image": {
                    "url": liveImageUrl
                }
            }

            await send_embed_to_webhook(embed)
            print(last_title)

            last_title = title  # 방송 제목 초기화
            is_live = True

            # print 후, 대기
            while check_naver_status() == 'OPEN':
                print("Checking for live title status")
                response = requests.get(Chzzk_api_url, headers=headers)
                title = response.json().get('content', {}).get('liveTitle')

                if last_title is not None and title != last_title:
                    embed = {
                        "description": f'## [{channel}님의 방제 변경!!](https://chzzk.naver.com/live/{Chzzk_channel_id})',
                        "color": 0x62c1cc,
                        "fields": [
                            {
                                "name": "방송 제목",
                                "value": '▶ ' + last_title,
                                "inline": True
                            },
                            {
                                "name": "변경 제목",
                                "value": '▶ ' + title,
                                "inline": True
                            }
                        ],
                        "author": {
                            "name": channel,
                            "icon_url": channelImageUrl
                        },
                        "image": {
                            "url": liveImageUrl
                        }
                    }
                    await send_embed_to_webhook(embed)

                last_title = title  # 방송 제목 초기화
                await asyncio.sleep(10)  # 10초마다 확인 (조절 가능)
        else:
            print("Not Open Status. Checking again in 10 seconds.")

            if is_live:
                embed = {
                    "description": f'## {channel}님의 방송 종료!!',
                    "color": 0x62c1cc,
                    "fields": [
                        {
                            "name": "다음 방송도 와주실거죠?",
                            "value": "",
                            "inline": False
                        }
                    ],
                    "author": {
                        "name": channel,
                        "icon_url": channelImageUrl
                    },
                    "image": {
                        "url": liveImageUrl
                    }
                }
                await send_embed_to_webhook(embed)
                is_live = False

            await asyncio.sleep(10)  # CLOSE 상태인 경우 10초마다 확인 (조절 가능)

# 메인 함수
async def main():
    await check_and_post_periodically()

# asyncio 이벤트 루프 실행
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
