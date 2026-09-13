import aiohttp
from . import config

async def msg(text):
	async with aiohttp.ClientSession() as session:
		await session.post(config.NTFY_URL,
			data=text.encode("utf-8"),
			headers={"Title": "Teh home"},
		)
