#!/usr/bin/python

from select import select
from socket import socket,SOL_SOCKET,SO_REUSEADDR
from traceback import format_exc
from time import ctime
import re,sys


import logging
logger = logging.getLogger("hmux")
#logger = logging

class HMUXClient:
	def __init__(self, sock, handler):
		self.socket = sock
		self.handler = handler
		self.buffer = ""
		self.lastsrc = ""

	def getSocket(self):
		return self.socket

	def send(self, data):
		sd = data
		#logger.debug("Will send %r"%(sd,))
		self.socket.sendall(sd)

	def sendCommand(self, command):
		data = u""
		found = False
		for n,x in enumerate(command):
			if found and x == u">":
				found = False
			elif found:
				data += chr(int(x))
			elif x == u"<":
				if command[n+1] in (u"1",u"2",u"3",u"4"):
					found = True
				else:
					data += x
			else:
				data += x
		self.send(data)

	def handleOnce(self):
		src = ""
		try:
			data = self.socket.recv(65000)
		except:
			data = ""
		if not data:
			self.close()
			return
		startbit = self.handler.startbit
		lines = re.split(self.handler.stopbit, (self.buffer+data))
		self.buffer = lines.pop()
		for line in lines:
			if startbit:
				if not startbit in line:
					logger.warning("No startbit before stopbit")
					logger.warning("%r"%(line,))
					continue
				head,data = line.split(self.handler.startbit,1)
			else:
				if "<SRC" in line:
					head,data = line.split("<SRC")[-1].split("\r\n",1)
					head = "<SRC"+head
				else:
					head,data = "", line
			if "<SRC" in head:
				src = head.split("<SRC")[-1]
				if ">" in src:
					src = src.split(">")[0]
					self.lastsrc = src
			else:
				src = self.lastsrc
			try:
				if src:
					self.handler.cb(data,src)
				else:
					self.handler.cb(data)

			except:
				logger.error("Error: Could not handle message")
				logger.error("%r"%(data,))
				logger.error(format_exc())

	def close(self):
		logger.info("Closing connection to HMUX")
		self.handler.removeClient(self)

class HMUXHandler:
	def __init__(self, port, startbit="\x01",stopbit="\x00"):
		self.port = port
		self.clients = []
		self.sockets = {}
		self.cb = None
		self.onConnect = None
		self.startbit = startbit
		self.stopbit = stopbit
		self.listen()

	def setOnConnect(self, callback):
		self.onConnect = callback

	def setCallback(self, callback):
		self.cb = callback

	def listen(self):
		self.socket = socket()
		self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
		self.socket.bind( ("",self.port) )
		self.socket.listen(10)

	def acceptClient(self, c):
		cs,ca = c.accept()
		cs.settimeout(1)
		logger.info("Got HMUX-connection from %r"%(ca,))
		client = HMUXClient(cs,self)
		self.clients.append(client)
		self.sockets[cs] = client
		if self.onConnect:
			self.onConnect()

	def removeClient(self,client):
		self.clients.remove(client)
		del self.sockets[client.getSocket()]

	def getSockets(self):
		return [self.socket] + [s for s in self.sockets]

	def handleSockets(self, socketList):
		for s in socketList:
			if s == self.socket:
				self.acceptClient(s)
			elif s in self.sockets:
				self.sockets[s].handleOnce()

	def send(self, data):
		for client in self.clients:
			try:
				client.send(data)
			except:
				logger.error("Got data: %r"%(data,))
				logger.error(format_exc())
	def serve_forever(self):
		while 1:
			socks = self.getSockets()
			x,y,z = select(socks,[],[])
			self.handleSockets(x)
