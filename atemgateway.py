#!/usr/bin/env python


import logging
from atem import AtemDevice
from hmux import HMUXHandler
from threading import Thread
from time import sleep
import os
import math

version = "1.0.0"

logging.basicConfig()
class AtemGateway:
	def __init__(self, ip, hmuxport,statusdest="HTC-Video"):
		self.hmux = HMUXHandler(hmuxport)
		self.hmux.setCallback(self.hmuxcb)
		self.atem = AtemDevice(ip,callback=self.atemcb)
		self.statusdest = statusdest
		self.destmap = {0:"PP",1:"ME"}
		self.tallycache = {}
		self.audiovolumes = {}
	def atemcb(self, cmd, args):
		if cmd == "program":
			me = self.destmap[args["me"]]
			src = args["src"]
			statusdest = self.statusdest
			self.report("KAYAK",me,"PGM",src)
		elif cmd == "preview":
			me = self.destmap[args["me"]]
			src = args["src"]
			statusdest = self.statusdest
			self.report("KAYAK",me,"PST",src)
		elif cmd == "audio":
			volume = args["volume"]
			self.audiovolumes[args["src"]] = volume
			self.report("AUDIO",args["src"],volume)
		elif cmd == "audiomaster":
			self.report("MASTER",args["volume"])
		elif cmd == "key":
			self.report("KEY",args["me"],args["keyer"],args["enabled"])
		elif cmd == "keyinfo":
			self.report("KEYINFO",args["me"],args["keyer"],args["keytype"],args["fillsrc"],args["keysrc"])
		elif cmd == "keyluma":
			self.report("KEYLUMA",args["me"],args["keyer"],args["premulti"],args["clip"],args["gain"],args["invert"])
		elif cmd == "dsk":
			if not args.get("trans"):
				self.report("DSK",args["keyer"],args["onair"])
		elif cmd == "dsksources":
			self.report("DSKSOURCES",args["keyer"],args["fillsrc"],args["keysrc"])
		elif cmd == "dsksetting":
			self.report("DSKSETTING",args["keyer"],
				args["tie"],args["premulti"],
				args["clip"],args["gain"],args["invert"],args["masked"],
				args["top"],args["bottom"],args["left"],args["right"],
			)
		elif cmd == "black":
			if not args.get("trans"):
				self.report("BLACK",args["me"],args["black"])
		elif cmd == "tally":
			sources = args["sources"]
			for source in sources:
				if source["dim"] != self.tallycache.get(source["src"]):
					self.tallycache[source["src"]] = source["dim"]
					self.report("TALLY",source["src"],source["dim"])
		elif cmd == "color":
			self.report("COLOR",args["generator"],args["src"])
		elif cmd in ["connect","disconnect","timeout"]:
			print "INFO;"+cmd
		elif cmd in ["videomodes","videoformat"]:
			pass
		else:
			print "WARN;ATEM",cmd,args
			
	def report(self, *args):
		if self.statusdest:
			data = "\x02".join([str(x) for x in args])
			self.hmux.send("<PORT"+self.statusdest+">\x01"+data+"\x00")
	def moveVolume(self,src,volume, frames):
		def moveThread(start,end,frames):
			pos = start
			speed = (end-start)/frames
			while (start<end and pos < end) or (start>end and pos > end):
				pos += speed
				#volume = int(min((pow(1000,pos)/1000),1.99)*32768)
				volume = int(pos*32768)
				volume = min(volume,65535)
				volume = max(volume,0)
				print "Vol",volume
				#if volume < 150: volume = 0
				self.atem.audioSettings(src,volume=volume)
				sleep(0.04)
			print start,end,frames,speed,pos
		start = self.audiovolumes[src]
		end = volume
		t = Thread(target=moveThread,args=(start,end,frames))
		t.start()
	def hmuxcb(self,data,src=None):
		print "HMUX",data,src
		args = data.split(":")
		cmd = args.pop(0)
		print cmd,args
		if cmd == "CUE":
			dst = args[0]
			src = int(args[1])
			if dst == "HB":
				self.atem.preview(src,me=0)
			elif dst == "BS":
				self.atem.preview(src,me=1)
		elif cmd == "PSTTAKE":
			dst = args[0]
			if dst == "HB":
				me = 0
			elif dst == "BS":
				me = 1
			mixtime = args[1]
			self.atem.transSettings(style=0,me=me) # Mix
			self.atem.mixSettings(int(mixtime),me=me)
			self.atem.auto(me=me)
		elif cmd in["TAKE"]:
			dst,src,mixtime,mix = args
			if dst == "HB":
				me = 0
			elif dst == "BS":
				me = 1
			elif dst.startswith("AUX"):
				me = -1
				aux = int(dst[3:])
			if me < 0:
				self.atem.aux(aux,int(src))
			else:
				if mix == "C":
					self.atem.program(int(src),me=me)
				elif mix == "M":
					self.atem.preview(int(src),me=me)
					self.atem.transSettings(style=0,me=me) # Mix
					self.atem.mixSettings(int(mixtime),me=me)
					self.atem.auto(me=me)
				elif mix == "W":
					self.atem.preview(int(src),me=me)
					self.atem.transSettings(style=2,me=me) # Wipe
					self.atem.wipeSettings(int(mixtime),me=me)
					self.atem.auto(me=me)
		elif cmd == "KEY":
			me,keyer,enabled = args
			self.atem.keyOn(int(enabled),me=int(me),keyer=int(keyer))
		elif cmd == "DSK":
			keyer,enabled = args
			self.atem.dskOn(int(keyer),int(enabled))
		elif cmd == "DSKSOURCES":
			keyer,fill,key = args
			self.atem.dskFill(int(keyer),int(fill))
			self.atem.dskKey(int(keyer),int(key))
		elif cmd == "DSKLUMA":
			keyer,premulti,clip,gain,invert = args
			self.atem.dskLuma(int(keyer),int(premulti),int(clip),int(gain),int(invert))
		elif cmd == "AUX":
			chan,src= args
			self.atem.aux(int(chan),int(src))
		elif cmd == "VOLUME":
			src,volume = args
			self.atem.audioSettings(int(src),volume=int(volume),option=1)
		elif cmd == "MASTERVOLUME":
			volume, = args
			self.atem.audioMaster(volume=int(volume))
		elif cmd == "MOVEVOLUME":
			src,volume,frames = args
			self.moveVolume(int(src),volume=float(volume)/127,frames=int(frames))
		elif cmd.startswith("MOVE\x02"):
			cmd,src,volume,frames = cmd.split("\x02")
			print cmd,src,volume,frames
			if int(frames) <= 0: frames = 1
			self.moveVolume(int(src),volume=float(volume),frames=int(frames))
		elif cmd.startswith("MVI"):
			mviewer,window,source = args
			self.atem.multiViewInput(int(mviewer),int(window),int(source))
		else:
			print "Unknown command",cmd,args
			
		
	def run(self):
		self.hmux.serve_forever()

	def getSockets(self):
		return self.hmux.getSockets()

	def handleSockets(self, sockets):
		return self.hmux.handleSockets(sockets)

if __name__ == '__main__':
	try:
		try:
			from daemonctl import dts
		except:
			import daemontools as dts
		name = os.path.basename(__file__).split(".")[0]
		dts.init(name)
		cfg = dts.cfg
	except Exception as e:
		print e
		dts = None
		cfg = {"server":"10.20.126.242","hmuxport":12345,"statusdest":"SONYMIXER"}
	agw = AtemGateway(cfg.get("server"),int(cfg.get("hmuxport")),cfg.get("statusdest"))
	if dts is None:
		agw.run()
	else:
		dts.addModule(agw)
		dts.serve_forever()

