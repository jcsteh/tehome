import os
import re
import time
import asyncio
import pjsua
from . import config, garage

class Account(pjsua.AccountCallback):
	def __init__(self, account):
		self._incomingCallFuture = None
		account.set_callback(self)

	def on_incoming_call(self, pjCall):
		call = Call(pjCall)
		if self._incomingCallFuture:
			loop.call_soon_threadsafe(self._incomingCallFuture.set_result, call)

	def waitForCall(self):
		self._incomingCallFuture = loop.create_future()
		return self._incomingCallFuture

class Call(pjsua.CallCallback):
	def __init__(self, call):
		self.call = call
		call.set_callback(self)
		self._dtmfFuture = None
		self._player = None

	def on_dtmf_digit(self, digit):
		#print("DTMF " + digit)
		if self._dtmfFuture:
			loop.call_soon_threadsafe(self._dtmfFuture.set_result, digit)

	def on_state(self):
		if (self._dtmfFuture and not self._dtmfFuture.done() and
				self.call.info().state == pjsua.CallState.DISCONNECTED):
			loop.call_soon_threadsafe(self._dtmfFuture.set_exception, EOFError())

	def waitForDtmf(self):
		self._dtmfFuture = loop.create_future()
		return self._dtmfFuture

	def play(self, fileName):
		fileName = os.path.join(os.path.dirname(__file__), fileName)
		if self._player:
			pj.player_destroy(self._player)
		self._player = pj.create_player(fileName)
		playerSlot = pj.player_get_slot(self._player)
		callSlot = self.call.info().conf_slot
		pj.conf_connect(playerSlot, callSlot)

	def hangup(self):
		if self._player:
			pj.player_destroy(self._player)
		self.call.hangup()

RE_CALLER = re.compile(r'^<sip:(\d+)@')
async def handler():
	global loop, pj
	loop = asyncio.get_event_loop()
	pj = pjsua.Lib()
	pj.init(log_cfg=pjsua.LogConfig(console_level=100))
	pj.set_null_snd_dev()
	pj.create_transport(pjsua.TransportType.UDP, pjsua.TransportConfig(5060))
	pj.start()
	pjAcc = pj.create_account(pjsua.AccountConfig(config.SIP_SERVER,
		config.SIP_USER, config.SIP_PW, config.SIP_SERVER))
	acc = Account(pjAcc)

	firstCallTime = 0
	while True:
		call = await acc.waitForCall()
		print("Got call")
		caller = RE_CALLER.match(call.call.info().remote_contact)
		if not caller or caller.group(1) not in config.PHONE_CALLERS:
			print("Rejecting unknown caller")
			call.call.hangup()
			continue
		print("Answering call")
		call.call.answer()
		await asyncio.sleep(1)
		if time.time() < firstCallTime + 15:
			# If a second call arrives within 15 seconds, open the garage door.
			firstCallTime = 0
			call.play("success.wav")
			await garage.set("TargetDoorState", 0)
		else:
			call.play("hello.wav")
			await asyncio.sleep(2)
			firstCallTime = time.time()
		print("Hanging up call")
		call.hangup()
