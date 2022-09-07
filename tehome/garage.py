import asyncio
import time
import bleak
import switchbot
from quart import request
from . import config, homebridge, web

OPEN = 0
CLOSED = 1
OPENING = 2
CLOSING = 3

ACC_NAME = "Garage door"
state = CLOSED
changeTime = 0

async def get(char):
	if char in ("CurrentDoorState", "TargetDoorState"):
		return state
	elif char == "ObstructionDetected":
		return False

async def getBot():
	dev = await bleak.BleakScanner.find_device_by_address(config.GARAGE_MAC)
	return switchbot.devices.bot.Switchbot(dev, password=config.GARAGE_PW)

async def set(char, val):
	global state
	if val == state:
		return # Already open/closed.
	print("Closing garage" if val == CLOSED else "Opening garage")
	bot = await getBot()
	await bot.press()
	state = OPENING if val == OPEN else CLOSING
	await homebridge.updateChar(ACC_NAME, "CurrentDoorState", state)

@web.app.route("/garageSensorReport")
async def onSensor():
	global state, changeTime
	tilt = request.args.get("tilt")
	if tilt:
		tilt = int(tilt)
		newState =  OPEN if tilt < 10 else CLOSED
		if newState != state:
			state = newState
			changeTime = time.time()
			print("Garage door %s" % ("open" if state == OPEN else "closed"))
		await homebridge.updateChar(ACC_NAME, "CurrentDoorState", state)
		await homebridge.updateChar(ACC_NAME, "TargetDoorState", state)
	return ''
