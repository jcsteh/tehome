"""Run the hot water relay when there is enough spare solar generation."""

import asyncio
import datetime
import json
from pathlib import Path

import requests
from requests.auth import HTTPDigestAuth

from . import config, fronius


POLL_SECONDS = 60
SAVE_INTERVAL = datetime.timedelta(minutes=15)
RELAY_ID = 0
SOLAR_THRESHOLD_WATTS = 2000
SOLAR_DELAY = datetime.timedelta(minutes=15)
MINIMUM_ON_TIME = datetime.timedelta(hours=1)
DAILY_HEATING_TARGET = datetime.timedelta(hours=3)
MAX_TIME_BETWEEN_HEATING = datetime.timedelta(hours=12)
SOLAR_START = datetime.time(11, 5)
SOLAR_END = datetime.time(15, 55)
BACKUP_START = datetime.time(2, 55)
BACKUP_END = datetime.time(5, 55)
stateFile = Path(__file__).with_name("hotWater.json")

# This state is persisted in hotWater.json.
state = {
	"heatingTime": datetime.timedelta(),
	"lastResetDate": None,
	"lastHeatingAt": None,
	"forcedHeatingActive": False,
}

# These values deliberately live only in memory. If the process is restarted
# while the relay is on, it is treated as having just turned on. That is
# conservative, and ensures the relay is not turned off within an hour of a
# restart when its actual on-time is unknown.
lastObservedAt = None
relayWasOn = False
relayOnSince = None
solarAboveSince = None
solarBelowSince = None
waitingForMinimumOnTime = False
lastSavedState = None
lastSavedAt = None


def getStateData():
	return {
		"heatingSeconds": state["heatingTime"].total_seconds(),
		"lastResetDate": (
			state["lastResetDate"].isoformat() if state["lastResetDate"] else None
		),
		"lastHeatingAt": (
			state["lastHeatingAt"].isoformat() if state["lastHeatingAt"] else None
		),
		"forcedHeatingActive": state["forcedHeatingActive"],
	}


def loadState():
	global lastSavedState

	try:
		data = json.loads(stateFile.read_text())
	except FileNotFoundError:
		return
	except (OSError, json.JSONDecodeError) as error:
		print(f"Error loading hot water state: {error}")
		return

	try:
		state.update({
			"heatingTime": datetime.timedelta(seconds=data["heatingSeconds"]),
			"lastResetDate": (
				datetime.date.fromisoformat(data["lastResetDate"])
				if data["lastResetDate"] is not None else None
			),
			"lastHeatingAt": (
				datetime.datetime.fromisoformat(data["lastHeatingAt"])
				if data["lastHeatingAt"] is not None else None
			),
			"forcedHeatingActive": data.get("forcedHeatingActive", False),
		})
	except (KeyError, TypeError, ValueError) as error:
		print(f"Invalid hot water state: {error}")
		return

	lastSavedState = getStateData()


def saveState(now, force=False):
	global lastSavedState, lastSavedAt

	data = getStateData()
	if data == lastSavedState:
		return
	if (
		not force
		and lastSavedAt
		and now - lastSavedAt < SAVE_INTERVAL
	):
		return

	temporaryStateFile = stateFile.with_name(stateFile.name + ".tmp")

	try:
		temporaryStateFile.write_text(json.dumps(data))
		temporaryStateFile.replace(stateFile)
	except OSError as error:
		print(f"Error saving hot water state: {error}")
		return
	lastSavedState = data
	lastSavedAt = now


loadState()


def shellyRequest(method, **params):
	"""Make an authenticated RPC request to the first Pro 2 relay."""
	response = requests.get(
		f"http://{config.HOT_WATER_ADDR}/rpc/{method}",
		params=params,
		auth=HTTPDigestAuth("admin", config.HOT_WATER_PW),
		timeout=10,
	)
	response.raise_for_status()
	return response.json()


def getRelayState():
	return shellyRequest("Switch.GetStatus", id=RELAY_ID)["output"]


def setRelay(on):
	shellyRequest("Switch.Set", id=RELAY_ID, on=str(on).lower())
	print(f"Turning hot water {'on' if on else 'off'}")


def resetIfNeeded(now):
	"""Start a new heating day at 11:05 AM."""

	if now.time() >= SOLAR_START and state["lastResetDate"] != now.date():
		state["heatingTime"] = datetime.timedelta()
		state["lastResetDate"] = now.date()
		state["forcedHeatingActive"] = False
		print("Reset hot water heating time")
		return True
	elif state["lastResetDate"] is None:
		# Before 11:05 AM, the current heating day began yesterday.
		state["lastResetDate"] = now.date() - datetime.timedelta(days=1)
		state["forcedHeatingActive"] = False
		return True
	return False


def recordRelayState(now, relayIsOn):
	"""Account for elapsed on-time and learn an on-time after a restart."""
	global lastObservedAt, relayWasOn, relayOnSince

	if lastObservedAt is not None and relayWasOn:
		state["heatingTime"] += now - lastObservedAt
	lastObservedAt = now

	if relayIsOn:
		state["lastHeatingAt"] = now
	if relayIsOn and not relayWasOn:
		relayOnSince = now
	elif not relayIsOn:
		relayOnSince = None
	relayWasOn = relayIsOn


def isSolarWindow(now):
	return SOLAR_START <= now.time() <= SOLAR_END


def updateSolarTimers(now, generation):
	"""Return whether solar has been continuously high or low for 15 minutes."""
	global solarAboveSince, solarBelowSince

	if generation > SOLAR_THRESHOLD_WATTS:
		solarAboveSince = solarAboveSince or now
		solarBelowSince = None
	else:
		solarBelowSince = solarBelowSince or now
		solarAboveSince = None

	return (
		solarAboveSince is not None and now - solarAboveSince >= SOLAR_DELAY,
		solarBelowSince is not None and now - solarBelowSince >= SOLAR_DELAY,
	)


def mayTurnOff(now):
	return (
		relayOnSince is None or now - relayOnSince >= MINIMUM_ON_TIME
	)


async def auto():
	"""Perform one poll and make any needed relay change."""
	global relayWasOn, solarAboveSince, solarBelowSince, waitingForMinimumOnTime

	now = datetime.datetime.now()
	relayIsOn = await asyncio.to_thread(getRelayState)
	relayStateChanged = relayIsOn != relayWasOn
	recordRelayState(now, relayIsOn)
	reset = resetIfNeeded(now)

	inSolarWindow = isSolarWindow(now)
	solarHigh = solarLow = False
	if inSolarWindow:
		flow = await asyncio.to_thread(fronius.getCurrentFlow)
		solarHigh, solarLow = updateSolarTimers(now, flow["P_PV"])
	else:
		solarAboveSince = None
		solarBelowSince = None

	# From 2:55 AM to 5:55 AM, grid heat only makes up the shortfall
	# from the preceding solar-heating day.
	inBackupWindow = BACKUP_START <= now.time() < BACKUP_END
	hasNotHeatedRecently = (
		state["lastHeatingAt"] is None
		or now - state["lastHeatingAt"] >= MAX_TIME_BETWEEN_HEATING
	)
	forcedHeatingChanged = False
	if (
		inSolarWindow
		and hasNotHeatedRecently
		and not state["forcedHeatingActive"]
	):
		state["forcedHeatingActive"] = True
		forcedHeatingChanged = True
	if (
		state["heatingTime"] >= DAILY_HEATING_TARGET
		and state["forcedHeatingActive"]
	):
		state["forcedHeatingActive"] = False
		forcedHeatingChanged = True

	shouldTurnOn = state["heatingTime"] < DAILY_HEATING_TARGET and (
		(inSolarWindow and (solarHigh or state["forcedHeatingActive"]))
		or inBackupWindow
	)
	shouldTurnOff = (
		state["heatingTime"] >= DAILY_HEATING_TARGET
		or (inSolarWindow and solarLow and not state["forcedHeatingActive"])
		or (not inSolarWindow and not inBackupWindow)
	)

	if shouldTurnOn and not relayIsOn:
		await asyncio.to_thread(setRelay, True)
		recordRelayState(now, True)
		relayStateChanged = True
		waitingForMinimumOnTime = False
	elif shouldTurnOff and relayIsOn:
		if mayTurnOff(now):
			await asyncio.to_thread(setRelay, False)
			recordRelayState(now, False)
			relayStateChanged = True
			if state["forcedHeatingActive"]:
				state["forcedHeatingActive"] = False
				forcedHeatingChanged = True
			waitingForMinimumOnTime = False
		elif not waitingForMinimumOnTime:
			print("Hot water is waiting for its one-hour minimum on-time")
			waitingForMinimumOnTime = True

	saveState(now, force=relayStateChanged or reset or forcedHeatingChanged)


async def poll():
	while True:
		try:
			await auto()
		except Exception as error:
			print(f"Error updating hot water: {error}")
		await asyncio.sleep(POLL_SECONDS)
