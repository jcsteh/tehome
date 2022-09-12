import aiohttp
from . import config

async def msg(text):
	async with aiohttp.ClientSession() as session:
		await session.post(config.SLACK_WEBHOOK, json={"text": text})
