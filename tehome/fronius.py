import datetime
import os

import requests
import sqlalchemy
from dateutil.relativedelta import relativedelta
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

from . import config

FRONIUS_URL = f"http://{config.FRONIUS_ADDR}/solar_api/v1"

Model = declarative_base()

class EnergyLog(Model):
	__tablename__ = "energy_log"
	time = Column(DateTime, primary_key=True)
	generated = Column(Integer)
	exported = Column(Integer)
	imported = Column(Integer)

class PreviousTotal(Model):
	__tablename__ = "previous_total"
	name = Column(String, primary_key=True)
	total = Column(Integer)

engine = sqlalchemy.create_engine(
	"sqlite:///" + os.path.join(os.path.dirname(__file__), "fronius.db"),
	future=True
)
session = sqlalchemy.orm.Session(engine)

def initDb():
	Model.metadata.create_all(engine)
	totals = getNewTotals()
	for name, total in totals.items():
		session.add(PreviousTotal(name=name, total=total))
	session.commit()

def froniusRequest(path):
	r = requests.get(f"{FRONIUS_URL}/{path}")
	r.raise_for_status()
	return r.json()

def getNewTotals():
	totals = {}
	inverters = froniusRequest("GetInverterRealtimeData.cgi?Scope=System")
	totals["generated"] = sum(
		inverters["Body"]["Data"]["TOTAL_ENERGY"]["Values"].values()
	)
	meters = froniusRequest("GetMeterRealtimeData.cgi?Scope=System")
	data = meters["Body"]["Data"]["0"]
	totals["exported"] = data["EnergyReal_WAC_Sum_Produced"]
	totals["imported"] = data["EnergyReal_WAC_Sum_Consumed"]
	return totals

def getPrevTotals():
	totals = {}
	for total in session.query(PreviousTotal).all():
		totals[total.name] = total.total
	return totals

def logData():
	newTotals = getNewTotals()
	prevTotals = getPrevTotals()
	deltas = {}
	for key in newTotals:
		deltas[key] = newTotals[key] - prevTotals[key]
	entry = EnergyLog(time=datetime.datetime.now(), **deltas)
	session.add(entry)
	for total in session.query(PreviousTotal).all():
		total.total = newTotals[total.name]
	session.commit()

def getDeltasDuring(start, end):
	deltas = next(session.execute(
		sqlalchemy.select(
			sqlalchemy.func.sum(EnergyLog.generated).label("generated"),
			sqlalchemy.func.sum(EnergyLog.exported).label("exported"),
			sqlalchemy.func.sum(EnergyLog.imported).label("imported")
		).where(EnergyLog.time >= start).where(EnergyLog.time <= end)
	))._asdict()
	deltas["used"] = (
		(deltas["generated"] or 0)
		- (deltas["exported"] or 0)
		+ (deltas["imported"] or 0)
	)
	return deltas

def getDeltasLastHour():
	now = datetime.datetime.now()
	hourAgo = now - datetime.timedelta(hours=1)
	return getDeltasDuring(hourAgo, now)

def getDeltasToday():
	todayStart = datetime.date.today()
	now = datetime.datetime.now()
	return getDeltasDuring(todayStart, now)

def getDeltasYesterday():
	today = datetime.date.today()
	yesterday = today - datetime.timedelta(days=1)
	return getDeltasDuring(yesterday, today)

def getDeltasThisWeek():
	today = datetime.date.today()
	weekStart = today - datetime.timedelta(days=today.weekday())
	now = datetime.datetime.now()
	return getDeltasDuring(weekStart, now)

def getDeltasLastWeek():
	today = datetime.date.today()
	thisWeek = today - datetime.timedelta(days=today.weekday())
	lastWeek = thisWeek - datetime.timedelta(weeks=1)
	return getDeltasDuring(lastWeek, thisWeek)

def getDeltasThisMonth():
	now = datetime.datetime.now()
	monthStart = datetime.date(now.year, now.month, 1)
	return getDeltasDuring(monthStart, now)

def getDeltasLastMonth():
	today = datetime.date.today()
	thisMonth = datetime.date(today.year, today.month, 1)
	lastMonth = thisMonth - relativedelta(months=1)
	return getDeltasDuring(lastMonth, thisMonth)

def getDeltasThisYear():
	now = datetime.datetime.now()
	yearStart = datetime.date(now.year, 1, 1)
	return getDeltasDuring(yearStart, now)

def getCurrentFlow():
	return froniusRequest("GetPowerFlowRealtimeData.fcgi")["Body"]["Data"]["Site"]

def showSummary():
	flow = getCurrentFlow()
	print(f"now: consumption {-flow['P_Load']}, ", end="")
	print(f"generating {flow['P_PV']}, ", end="")
	if flow["P_Grid"] > 0:
		print(f"importing {flow['P_Grid']}")
	else:
		print(f"exporting {-flow['P_Grid']}")
	for name, func in (
		("last hour", getDeltasLastHour),
		("today", getDeltasToday),
		("yesterday", getDeltasYesterday),
		("this week", getDeltasThisWeek),
		("last week", getDeltasLastWeek),
		("this month", getDeltasThisMonth),
		("last month", getDeltasLastMonth),
		("this year", getDeltasThisYear),
	):
		deltas = func()
		print(f"{name}: ", end="")
		summary = []
		for key in ("used", "generated", "exported", "imported"):
			summary.append(f"{key} {deltas[key]}")
		print(", ".join(summary))
