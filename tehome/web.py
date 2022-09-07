import asyncio
from hypercorn.asyncio import serve
from hypercorn.config import Config
from quart import Quart
from . import config

qconfig = Config()
qconfig.bind = config.WEB_BIND

app = Quart("tehome")

async def handler():
	await serve(app, qconfig,
		# Disable hypercorn's default signal handling.
		shutdown_trigger=lambda: asyncio.Future())
