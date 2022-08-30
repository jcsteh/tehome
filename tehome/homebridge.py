import os
import json
import asyncio
import websockets
from . import garage, airtouch

async def connect():
	global bridge
	bridge = await websockets.connect("ws://localhost:4050/")

async def send(msg):
	#print("Send: %s" % msg)
	await bridge.send(json.dumps(msg))

async def updateChar(name, char, val):
	await send({"topic": "set", "payload":
		{"name": name, "characteristic": char, "value": val}})

async def handler():
	await connect()
	while True:
		msg = json.loads(await bridge.recv())
		#print("Recv: %s" % msg)
		topic = msg["topic"]
		payload = msg["payload"]
		name = payload["name"]
		char = payload["characteristic"]
		if topic == "get":
			if name == garage.ACC_NAME:
				getter = garage.get(char)
			elif name.startswith(airtouch.ACC_PREFIX):
				getter = airtouch.get(int(name[-1]), char)
			else:
				continue
			try:
				val = await getter
			except Exception as e:
				print("Error getting: %s" % e)
				continue
			if val is None:
				continue
			reply = {"topic": "callback", "payload":
				{"name": name, "characteristic": char, "value": val}}
			await send(reply)
		elif topic == "set":
			val = payload["value"]
			if name == garage.ACC_NAME:
				setter = garage.set(char, val)
			elif name.startswith(airtouch.ACC_PREFIX):
				setter = airtouch.set(int(name[-1]), char, val)
			else:
				continue
			try:
				await setter
			except Exception as e:
				print("Error setting: %s" % e)
				continue

async def addAccessory(name, service):
	await send(msg = {"topic": "add", "payload":
		{"name": name, "service": service}})
	reply = await bridge.recv()
	print("Recv: %s" % reply)

async def setup():
	await connect()
	await addAccessory(garage.ACC_NAME, "GarageDoorOpener")
	await airtouch.airtouch.UpdateInfo()
	for group in airtouch.airtouch.groups:
		await addAccessory("%s%d" % (ACC_AIRTOUCH_PREFIX, group), "Thermostat")
