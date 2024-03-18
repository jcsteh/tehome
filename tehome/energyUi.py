import asyncio
import datetime

from quart import request

from . import fronius, web

def formatTableBegin(heading, firstCol):
	return (
		f'<h2>{heading}</h2>\n<table>\n'
		f'<tr><th>{firstCol}</th><th>Consumption</th><th>Generation</th><th>Export</th><th>Import</th></tr>\n'
	)

def formatRow(name, *values):
	out = f'<tr><th>{name}</th>'
	for val in values:
		out += f'<td>{fronius.formatVal(val)}</td>'
	out += '</tr>\n'
	return out

def getHtmlReport():
	out = []
	out.append(
		'<html>\n<head>\n<title>Energy Report</title>\n</head\n>'
		'<body>\n<h1>Energy Report</h1>\n'
	)
	out.append(formatTableBegin("Overview", "When"))
	flow = fronius.getCurrentFlow()
	consumption = -flow["P_Load"]
	generation = flow["P_PV"]
	if flow["P_Grid"] > 0:
		importing = flow["P_Grid"]
		exporting = 0
	else:
		exporting = -flow["P_Grid"]
		importing = 0
	out.append(formatRow("now", consumption, generation, exporting, importing))
	for name, func in (
		("last hour", fronius.getDeltasLastHour),
		("today", fronius.getDeltasToday),
		("yesterday", fronius.getDeltasYesterday),
		("this week", fronius.getDeltasThisWeek),
		("last week", fronius.getDeltasLastWeek),
		("this month", fronius.getDeltasThisMonth),
		("last month", fronius.getDeltasLastMonth),
		("this year", fronius.getDeltasThisYear),
	):
		deltas = func()
		out.append(formatRow(
			name,
			deltas["consumed"],
			deltas["generated"],
			deltas["exported"],
			deltas["imported"]
		))
	out.append('</table>\n')
	out.append(formatTableBegin("Today", "Hour"))
	today = datetime.date.today()
	for deltas in fronius.getDeltasForDay(today):
		out.append(formatRow(
			deltas["name"],
			deltas["consumed"],
			deltas["generated"],
			deltas["exported"],
			deltas["imported"]
		))
	out.append('</table>\n')
	out.append(formatTableBegin("Yesterday", "Hour"))
	yesterday = today - datetime.timedelta(days=1)
	for deltas in fronius.getDeltasForDay(yesterday):
		out.append(formatRow(
			deltas["name"],
			deltas["consumed"],
			deltas["generated"],
			deltas["exported"],
			deltas["imported"]
		))
	out.append('</table>\n')
	out.append('</body>\n</html>\n')
	return "".join(out)

@web.app.route("/energyInfo")
async def onEnergyInfo():
	return await asyncio.to_thread(getHtmlReport)
