from quart import request
from . import config, homebridge, web

ACC = "Flood sensor"

@web.app.route("/floodSensorReport")
async def onFloodSensor():
	flood = request.args.get("flood")
	await homebridge.updateChar(ACC, "LeakDetected", int(flood))
	batV = float(request.args.get("batV"))
	print(f"flood batV {batV}")
	await homebridge.updateChar(ACC, "StatusLowBattery", 1 if batV < 2.3 else 0)
	return ""
