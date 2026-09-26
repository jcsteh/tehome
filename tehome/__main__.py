import asyncio
from . import (
	homebridge, airtouch, web, homekit, energyUi, garage, doorbell, flood,
)

async def main():
	await asyncio.gather(
		homebridge.handler(),
		airtouch.poll(),
		#phone.handler(),
		web.handler(),
		homekit.poll(),
		#garage.batteryChecker(),
		doorbell.handler(),
	)

if __name__ == "__main__":
	asyncio.run(main())
