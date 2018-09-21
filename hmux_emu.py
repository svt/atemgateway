#!/usr/bin/env python
# -*- coding: utf-8 -*-

from socket import *
from select import select
from sys import stdin,argv

config = dict()
#exec(open("config.py").read(),config)
if len(argv) > 1:
	host = argv[1]
else:
	host = "localhost"

sock = socket()
sock.connect( (host,config.get("hmuxport",12345)) )
print "Connected"
running = True
while running:
	r,w,e = select((sock,stdin), (), (), 1)
	if stdin in r:
		sdata = ""
		data = stdin.readline()
		sp = data.split()
		if data[0] == "p":
			sdata = "<SRCHTC-Video>\r\n\x01CUE:HB:%s\x00"%data[1]
		elif data[0] == "t":
			sdata = "<SRCHTC-Video>\r\n\x01TAKE:HB:%s:6:M\x00"%data[1]
		elif data[0] == "w":
			sdata = "<SRCHTC-Video>\r\n\x01TAKE:HB:%s:7:W\x00"%data[1]
		elif data[0] == "k":
			sdata = "<SRCHTC-Video>\r\n\x01KEY:0:0:%s\x00"%data[1]
		elif data[0] == "v":
			sdata = "<SRCHTC-Video>\r\n\x01VOLUME:%s:%s\x00"%(sp[1],sp[2])
		elif sp[0] == "mv":
			sdata = "<SRCHTC-Video>\r\n\x01MASTERVOLUME:%s\x00"%(sp[1])
		elif sp[0] == "a":
			sdata = "<SRCHTC-Video>\r\n\x01AUX:%s:%s\x00"%(sp[1],sp[2])
		elif sp[0] == "d":
			sdata = "<SRCHTC-Video>\r\n\x01DSK:%s:%s\x00"%(sp[1],sp[2])
		elif sp[0] == "s":
			sdata = "<SRCHTC-Video>\r\n\x01DSKSOURCES:0:%s:%s\x00"%(sp[1],sp[2])
		elif sp[0] == "l":
			sdata = "<SRCHTC-Video>\r\n\x01DSKLUMA:0:0:%s:%s:0\x00"%(sp[1],sp[2])
		elif sp[0] == "m":
			sdata = "<SRCHTC-Video>\r\n\x01MOVEVOLUME:%s:%s:%s\x00"%(sp[1],sp[2],sp[3])
		elif sp[0] == "mvi":
			sdata = "<SRCHTC-Video>\r\n\x01MVI:%s:%s:%s\x00"%(sp[1],sp[2],sp[3])
		if sdata:
			sock.send(sdata)
			print "Sent:",repr(sdata)
	if sock in r:
		data = sock.recv(4096)
		if not data:
			while 1:
				try:
					sock = socket()
					sock.connect( (host,config.get("hmuxport",12345)) )
					break
				except:
					pass
			#running = False
			continue
		print "Recv:",repr(data)

