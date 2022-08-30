import asyncio
from . import config, homebridge
import airtouch4pyapi

ACC_PREFIX = "AirTouch zone "
airtouch = airtouch4pyapi.AirTouch(config.AIRTOUCH_ADDR)

async def updateChar(group, char):
	name = "%s%d" % (ACC_PREFIX, group)
	val = await get(group, char)
	await homebridge.updateChar(name, char, val)

def getTemp(group):
	if group == 3:
		# TV room has no sensor. Use the main unit sensor.
		return airtouch.acs[0].Temperature
	return airtouch.groups[group].Temperature

async def auto():
	for g in airtouch.groups:
		temp = getTemp(g)
		if ((config.AIRTOUCH_HEAT and temp >= config.AIRTOUCH_TEMP) or
				(not config.AIRTOUCH_HEAT and temp <= config.AIRTOUCH_TEMP)):
			print("Air group %d reached target temp, turning off" % g)
			await airtouch.TurnGroupOff(g)
	if airtouch.acs[0].PowerState == 'On' and all(g.PowerState == 'Off' for g in airtouch.groups.values()):
		print("Turning off air main")
		await airtouch.TurnAcOff(0)
		return
	if airtouch.acs[0].PowerState == 'Off' and any(g.PowerState == 'On' for g in airtouch.groups.values()):
		print("Turning on air main")
		await airtouch.TurnAcOn(0)

async def poll():
	# Hack to deal with airtouch4pyapi suppressing CancelledError.
	await asyncio.sleep(0.1)
	try:
		await airtouch.UpdateInfo()
	except Exception as e:
		print("Error updating AirTouch info: %s" % e)
	while True:
		await asyncio.sleep(60)
		while True:
			try:
				await airtouch.UpdateInfo()
				if hasattr(airtouch.acs[0], "Temperature"):
					break
			except Exception as e:
				pass
			await asyncio.sleep(1)
		try:
			await auto()
			for group in airtouch.groups:
				for char in ("CurrentTemperature", "CurrentHeatingCoolingState"):
					await updateChar(group, char)
		except Exception as e:
			print("Error in AirTouch auto/update: %s" % e)

async def get(group, char):
	if char == "TargetTemperature":
		return config.AIRTOUCH_TEMP
	if char == "CurrentTemperature":
		return getTemp(group)
	if char in ("CurrentHeatingCoolingState", "TargetHeatingCoolingState"):
		if airtouch.groups[group].PowerState == "On":
			# 1 is heat.
			return 1 if config.AIRTOUCH_HEAT else 2
		return 0 # Off
	if char == "TemperatureDisplayUnits":
		return 0 # Celsius

async def set(group, char, value):
	if char == "TargetHeatingCoolingState":
		if value > 0:
			print("Turning on air group %d" % group)
			await airtouch.TurnGroupOn(group)
		else:
			print("Turning off air group %d" % group)
			await airtouch.TurnGroupOff(group)
		await updateChar(group, "CurrentHeatingCoolingState")
		await auto()
