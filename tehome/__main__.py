import asyncio
from . import homebridge, airtouch, phone, web, homekit, energyUi, garage

async def main():
	await asyncio.gather(
		homebridge.handler(),
		airtouch.poll(),
		phone.handler(),
		web.handler(),
		homekit.poll(),
		garage.batteryChecker(),
	)

if __name__ == "__main__":
	asyncio.run(main())
