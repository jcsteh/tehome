"""Get data from native HomeKit sensors which don't have an alternative
interface. To do this, we have a fake switch which we activate periodically.
An Apple Home automation responds to this and sends us data via a web URL.
"""

import asyncio
from quart import request
from . import config, homebridge, web

ACC = "Homebridge periodic tasks"
joshTemp = 0.0

@web.app.route("/homekitData")
async def onHomekitData():
	global joshTemp
	# The temperature includes a degrees C suffix which we must strip.
	joshTemp = float(request.args.get("joshTemp")[:-2])
	return ""

async def poll():
	# hack: Wait for the web server to start.
	await asyncio.sleep(5)
	while True:
		# This will trigger the Apple Home automation, which will hit the URL defined
		# above.
		await homebridge.updateChar(ACC, "ProgrammableSwitchEvent", 0)
		await asyncio.sleep(300)
