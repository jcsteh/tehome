import asyncio
from . import homebridge, airtouch, phone

async def main():
	await asyncio.gather(
		homebridge.handler(),
		airtouch.poll(),
		phone.handler(),
	)

if __name__ == "__main__":
	asyncio.run(main())
