import asyncio
from . import homebridge, airtouch, phone, web, homekit, energyUi

async def main():
	await asyncio.gather(
		homebridge.handler(),
		airtouch.poll(),
		phone.handler(),
		web.handler(),
		homekit.poll(),
	)

if __name__ == "__main__":
	asyncio.run(main())
