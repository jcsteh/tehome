import asyncio
import bleak
import switchbot
from . import config, homebridge

ACC_NAME = "Garage door"
isOpen = False

async def get(char):
	if char in ("CurrentDoorState", "TargetDoorState"):
		return 0 if isOpen else 1
	elif char == "ObstructionDetected":
		return False

async def getBot():
	dev = await bleak.BleakScanner.find_device_by_address(config.GARAGE_MAC)
	return switchbot.devices.bot.Switchbot(dev, password=config.GARAGE_PW)

async def set(char, val):
	global isOpen
	print("opening garage")
	bot = await getBot()
	await bot.press()
	await asyncio.sleep(5)
	isOpen = val == 0
	await homebridge.updateChar(ACC_NAME, "CurrentDoorState", val)
