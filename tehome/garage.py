import asyncio
import bleak
import switchbot
from quart import request
from . import config, homebridge, slack, web

OPEN = 0
CLOSED = 1
OPENING = 2
CLOSING = 3

DOOR_ACC = "Garage door"
TEMP_ACC = "Garage temperature"
LUX_ACC = "Garage light sensor"
TOO_LONG_ACC = "Garage door open too long"
state = CLOSED
doorNotifyTask = None
botBattery = None

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
	await homebridge.updateChar(DOOR_ACC, "CurrentDoorState", state)

@web.app.route("/garageSensorReport")
async def onGarageSensor():
	global state, doorNotifyTask
	tilt = request.args.get("tilt")
	if tilt:
		tilt = int(tilt)
		newState =  OPEN if tilt < 10 else CLOSED
		if newState != state:
			state = newState
			if doorNotifyTask:
				doorNotifyTask.cancel()
			if state == OPEN:
				print("Garage door open")
				doorNotifyTask = asyncio.create_task(notifyOpenTooLong())
			else:
				print("Garage door closed")
				await homebridge.updateChar(TOO_LONG_ACC, "MotionDetected", 0)
		await homebridge.updateChar(DOOR_ACC, "CurrentDoorState", state)
		await homebridge.updateChar(DOOR_ACC, "TargetDoorState", state)
	temp = request.args.get("temp")
	if temp:
		temp = float(temp)
		await homebridge.updateChar(TEMP_ACC, "CurrentTemperature", temp)
	lux = request.args.get("lux")
	if lux:
		lux = int(lux)
		lux = max(lux, 0.0001) # HomeKit minimum.
		await homebridge.updateChar(LUX_ACC, "CurrentAmbientLightLevel", lux)
	return ''

async def notifyOpenTooLong():
	await asyncio.sleep(300)
	await homebridge.updateChar(TOO_LONG_ACC, "MotionDetected", 1)

async def batteryChecker():
	global botBattery
	while True:
		# Run every 24 hours.
		await asyncio.sleep(86400)
		bot = await getBot()
		info = await bot.get_basic_info()
		newBat = info["battery"]
		print(f"garage bot battery {newBat}%")
		if newBat <= 10 and newBat != botBattery:
			botBattery = newBat
			await slack.msg(f"garage bot battery {newBat}%")
