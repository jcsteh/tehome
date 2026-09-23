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

def formatCostTableBegin():
	return (
		'<h2>Cost</h2>\n<table>\n'
		'<tr><th>When</th><th>Imported</th><th>Energy charge</th>'
		'<th>Exported</th><th>Feed-in credit</th><th>Supply charge</th>'
		'<th>Net cost</th></tr>\n'
	)

def formatEnergy(val):
	return f'{fronius.formatVal(val / 1000)}kWh'

def formatCost(val):
	return f'${val / 100:.2f}'

def formatCostRow(name, cost, tariff=None, divisor=1):
	if tariff is not None:
		values = (tariff["imported"] / divisor, tariff["energyCharge"] / divisor)
		out = f'<tr><th>{name} — {tariff["name"]}</th>'
		out += f'<td>{formatEnergy(values[0])}</td><td>{formatCost(values[1])}</td>'
		out += '<td></td><td></td><td></td><td></td></tr>\n'
		return out
	values = (
		cost["imported"] / divisor,
		cost["energyCharge"] / divisor,
		cost["exported"] / divisor,
		-cost["feedInCredit"] / divisor,
		cost["supplyCharge"] / divisor,
		cost["netCost"] / divisor,
	)
	return (
		f'<tr><th>{name}</th><td>{formatEnergy(values[0])}</td>'
		f'<td>{formatCost(values[1])}</td><td>{formatEnergy(values[2])}</td>'
		f'<td>{formatCost(values[3])}</td><td>{formatCost(values[4])}</td>'
		f'<td>{formatCost(values[5])}</td></tr>\n'
	)

def formatCostGroup(name, cost, divisor=1):
	out = []
	for tariff in cost["tariffs"]:
		out.append(formatCostRow(name, cost, tariff, divisor))
	out.append(formatCostRow(f'{name} — total', cost, divisor=divisor))
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
	out.append(formatCostTableBegin())
	today = datetime.date.today()
	todayStart = datetime.datetime.combine(today, datetime.time.min)
	tomorrowStart = todayStart + datetime.timedelta(days=1)
	yesterdayStart = todayStart - datetime.timedelta(days=1)
	monthStart = todayStart.replace(day=1)
	completedMonthDays = max((todayStart - monthStart).days, 1)
	costRanges = [
		("Today", todayStart, datetime.datetime.now(), 1, 1),
		("Yesterday", yesterdayStart, todayStart, 1, 1),
		("This month", monthStart, tomorrowStart, (tomorrowStart - monthStart).days, 1),
	]
	if todayStart > monthStart:
		costRanges.append(
			("Month daily average", monthStart, todayStart,
			 completedMonthDays, completedMonthDays)
		)
	for name, start, end, days, divisor in costRanges:
		cost = fronius.getCostDuring(start, end, days)
		out.extend(formatCostGroup(name, cost, divisor))
	out.append('</table>\n')
	out.append(formatTableBegin("Today", "Hour"))
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
	out.append(formatTableBegin("Last 7 Days", "Hour"))
	for deltas in fronius.getDeltasForLastDays():
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
