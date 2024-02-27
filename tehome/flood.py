from quart import request
from . import config, homebridge, web

ACC = "Flood sensor"

@web.app.route("/floodSensorReport")
async def onFloodSensor():
	flood = request.args.get("flood")
	await homebridge.updateChar(ACC, "LeakDetected", int(flood))
	return ""
