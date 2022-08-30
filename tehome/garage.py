import asyncio
import switchbotpy
from . import config, homebridge

ACC_NAME = "Garage door"
bot = switchbotpy.Bot(bot_id=0, name="Garage door", mac=config.GARAGE_MAC)
bot.encrypted(config.GARAGE_PW)
isOpen = False

async def get(char):
	if char in ("CurrentDoorState", "TargetDoorState"):
		return 0 if isOpen else 1
	elif char == "ObstructionDetected":
		return False

async def set(char, val):
	global isOpen
	bot.press()
	print("opening garage")
	await asyncio.sleep(5)
	isOpen = val == 0
	await homebridge.updateChar(ACC_NAME, "CurrentDoorState", val)
