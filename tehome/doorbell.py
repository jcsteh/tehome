import asyncio
import datetime
import json
from google.cloud import pubsub_v1
from . import config, homebridge

CHIME_ACC = "Doorbell"

def callback(message):
	payload = json.loads(message.data.decode("utf-8"))
	message.ack()
	if payload.get("eventThreadState", "STARTED") != "STARTED":
		return
	events = payload.get("resourceUpdate", {}).get("events")
	if not events:
		return
	if events.get("sdm.devices.events.DoorbellChime.Chime"):
		print("Doorbell pressed")
		now = datetime.datetime.now()
		if config.DOORBELL_START_TIME <= (now.hour, now.minute) <= config.DOORBELL_END_TIME:
			asyncio.run_coroutine_threadsafe(
				homebridge.updateChar(CHIME_ACC, "ProgrammableSwitchEvent", 0),
				loop
			)
	if events.get("sdm.devices.events.CameraPerson.Person"):
		print("Doorbell: person detected")

async def handler():
	global loop
	loop = asyncio.get_event_loop()
	subscriber = pubsub_v1.SubscriberClient()
	streamingPull = subscriber.subscribe(config.GOOGLE_SUBSCRIPTION, callback=callback)
	await asyncio.to_thread(streamingPull.result)
