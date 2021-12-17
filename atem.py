#!/usr/bin/env python
# coding: utf-8
# Atem video switcher control module
#
# Protocol documentation found at http://skaarhoj.com/fileadmin/BMDPROTOCOL.html

import sys
from socket import socket,AF_INET,SOCK_DGRAM
from threading import Thread,Event
from time import time
from struct import pack,unpack
from traceback import print_exc


# Videomodes taken from libqatemcontrol
# https://github.com/petersimonsson/libqatemcontrol/blob/master/qatemconnection.cpp
videomodes = {
0: ("525i59.94 NTSC",(720, 525),29.97),
1: ("625i50 PAL",(720, 625),25),
2: ("525i59.94 NTSC 16:9", (864, 525), 29.97),
3: ("625i50 PAL 16:9", (1024, 625), 25),
4: ("720p50", (1280, 720), 50),
5: ("720p59.94", (1280, 720), 59.94),
6: ("1080i50", (1920, 1080), 25),
7: ("1080i59.94", (1920, 1080), 29.97),
8: ("1080p23.98", (1920, 1080), 23.98),
9: ("1080p24", (1920, 1080), 24),
10: ("1080p25", (1920, 1080), 25),
11: ("1080p29.97", (1920, 1080), 29.97),
12: ("1080p50", (1920, 1080), 50),
13: ("1080p59.94", (1920, 1080), 59.94),
14: ("2160p23.98", (3840, 2160), 23.98),
15: ("2160p24", (3840, 2160), 24),
16: ("2160p25", (3840, 2160), 25),
17: ("2160p29.97", (3840, 2160), 29.97),
}

class MaskDefault:
    def __init__(self):
        self.mask = 0
    def getValueOrZero(self, value, mask):
        if value is None:
            return 0
        else:
            self.mask |= mask
            return value

def str2hex(string):
    return " ".join(["%02x"%ord(x) for x in string])

def checkByteList(bytelist):
    for b in bytelist:
        if b > 255 or b < 0:
            raise ValueError("Byte not within sane values %r"%(b,))
    return bytelist

def int16(num):
    return checkByteList([ord(x) for x in pack("!h",num)])

def uint16(num):
    return checkByteList([num>>8, num&0xFF])

def uint32(num):
    return checkByteList([(num>>24)&0xFF, (num>>16)&0xFF, (num>>8)&0xFF, num&0xFF])

class AtemConnection(Thread):
    def __init__(self, ip, port=9910,callback=None):
        Thread.__init__(self)
        self.daemon = True
        self.ip = ip
        self.port = port
        self.sessionid = 0x53AB
        self.packetIdCounter = 0
        self.udp = socket(AF_INET,SOCK_DGRAM)
        self.udp.settimeout(2)
        self.cb = callback
        self.lastHB = 0
        self.connected = False
        self.replyEvent = Event()
    def send(self, data):
        self.udp.sendto(data,(self.ip,self.port))
        
    def recv(self,size=65535):
        data = self.udp.recvfrom(size)[0]
        return data
    def recvCmd(self):
        data = self.recv()
        #print repr(data)
        #print len(data)
        cmd = ord(data[0]) >> 3
        size = (ord(data[0]) & 0x07) << 8
        size += ord(data[1])
        sessionid = ord(data[2]) << 8
        sessionid += ord(data[3])
        #remoteid = ord(data[4]) << 8
        #remoteid += ord(data[5])
        remoteid = ord(data[10]) << 8
        remoteid += ord(data[11])
        args = data[12:]
        #print cmd,size
        #print sessionid,remoteid
        self.sessionid = sessionid
        if (cmd & 0x03):
            self.sendAck(remoteid)
        return cmd,args
        
    def getHead(self,cmd,data=[],remoteid=0):
        buffer = [0]*12
        size = 12+len(data)
        buffer[0] = (cmd << 3) + ((size >> 8)& 0x7)
        buffer[1] = size & 0xFF
        buffer[2] = self.sessionid >> 8
        buffer[3] = self.sessionid & 0xFF
        buffer[4] = remoteid >> 8
        buffer[5] = remoteid & 0xFF
        if cmd not in [0x2,0x10,0x8]: # Hello, Ack, RequestNextAfter
            self.packetIdCounter += 1
            buffer[10] = self.packetIdCounter >> 8
            buffer[11] = self.packetIdCounter & 0xFF
        return buffer + data
    def sendPacket(self, data):
        chars = [chr(x) for x in data]
        string = "".join(chars)
        self.send(string)
    def sendAck(self,remoteid=0):
        head = self.getHead(0x10,remoteid=remoteid)
        head[9] = 0x03
        self.sendPacket(head)
    def sendCmd(self,cmd,args):
        data = []
        size = len(args)+8
        data.append(size>>8)
        data.append(size&0xFF)
        data.append(0)
        data.append(0)
        for c in cmd: data.append(ord(c))
        out = self.getHead(0x01,data+args)
        self.replyEvent.clear()
        print "Sending:"," ".join(["%02X"%x for x in out])
        self.sendPacket(out)
        self.replyEvent.wait(0.1)
    def connect(self):
        self.sessionid = 0x53AB
        self.packetIdCounter = 0
        data = [0x01] + ([0x00]*7)
        head = self.getHead(0x2,data)
        head[9] = 0x3a
        self.sendPacket(head)
        cmd,args = self.recvCmd()
        self.connected = True
        self.replyEvent.set()
    def parsePacket(self, data):
        while data:
            size = ord(data[0])<<8
            size += ord(data[1])
            cmddata = data[4:size]
            data = data[size:]
            cmd = cmddata[:4]
            args = cmddata[4:]
            #print "SIZE",size,len(cmd)+4
            if size == len(cmddata)+4:
                self.cb(cmd,args)
    def run(self):
        while 1:
            now = time()
            if not self.connected:
                try:
                    self.connect()
                    if self.cb:
                        self.cb("connect",[])
                except:
                    if self.cb:
                        self.cb("timeout",[])
                    continue
            try:
                cmd,data = self.recvCmd()
            except:
                self.connected = False
                if self.cb:
                    self.cb("disconnect",[])
                continue
            self.lastHB = now
            if data:
                self.replyEvent.set()
                if self.cb:
                    self.parsePacket(data)
        
class AtemDevice:
    def __init__(self, ip, callback=None):
        self.callback = callback
        self.ac = AtemConnection(ip,callback=self.parseCmd)
        self.ac.start()
        self.videomodes = dict()
        self.videomode = -1
        self.srcNames = {}
    def cb(self,cmd,args):
        try:
            self.callback(cmd,args)
        except:
            print_exc()
    def reconnect(self):
        self.ac.connect()
    def program(self,src,me=0):
        self.ac.sendCmd("CPgI",[me, 0, src>>8, src&0xFF])
    def preview(self,src,me=0):
        self.ac.sendCmd("CPvI",[me, 0, src>>8, src&0xFF])
    def keyOn(self,enabled,me=0,keyer=0):
        self.ac.sendCmd("CKOn",[me,keyer,1 if enabled else 0,0])
    def keyType(self,keytype,keyer=0,me=0):
        self.ac.sendCmd("CKTp",[3,me,keyer,keytype,0,0,0,0])
    def keyFill(self,src,me=0,keyer=0):
        self.ac.sendCmd("CKeF",[me,keyer,src>>8,src&0xFF])
    def keyCut(self,src,me=0,keyer=0):
        self.ac.sendCmd("CKeC",[me,keyer,src>>8,src&0xFF])
    def keyChroma(self, me=0, keyer=0, hue=None, gain=None, ysup=None, lift=None, narrow=None):
        mask = 0
        if hue is not None:
            mask |= (1<<0)
        else:
            hue = 0
        if gain is not None:
            mask |= (1<<1)
        else:
            gain = 0
        if ysup is not None:
            mask |= (1<<2)
        else:
            ysup = 0
        if lift is not None:
            mask |= (1<<3)
        else:
            lift = 0
        if narrow is not None:
            mask |= (1<<4)
        else:
            narrow = 0
        self.ac.sendCmd("CKCk",[mask,me,keyer,0]
                + uint16(hue)
                + uint16(gain)
                + uint16(ysup)
                + uint16(lift)
                + [narrow, 0, 0, 0]
                )
    def dskFill(self,keyer,src):
        self.ac.sendCmd("CDsF",[keyer,0]+uint16(src))
    def dskKey(self,keyer,src):
        self.ac.sendCmd("CDsC",[keyer,0]+uint16(src))
    def dskOn(self,keyer,enabled):
        self.ac.sendCmd("CDsL",[keyer,enabled,0,0])
    def dskTie(self,keyer,tie):
        self.ac.sendCmd("CDsT",[keyer,tie,0,0])
    def dskRate(self,keyer,rate):
        self.ac.sendCmd("CDsR",[keyer,rate,0,0])
    def dskAuto(self,keyer):
        self.ac.sendCmd("DDsA",[keyer,0,0,0])
    def dskLuma(self,keyer,premulti=None,clip=None,gain=None,invert=None):
        mask = 0
        if premulti is None:
            premulti = 0
        else:
            mask += 1
        if clip is None:
            clip = 0
        else:
            mask += 2
        if gain is None:
            gain = 0
        else:
            mask += 4
        if invert is None:
            invert = 0
        else:
            mask += 8
        self.ac.sendCmd("CDsG",[mask,keyer,premulti,0]+uint16(int(clip*10.0))+uint16(int(gain*10.0))+[invert,0,0,0])
    def dskMask(self,keyer,masked=None,top=None,bottom=None,left=None,right=None):
        mask = 0
        self.sc.sendCmd("CDsM",[mask,keyer,masked,0]+
            uint16(int(top*1000.0))+
            uint16(int(bottom*1000.0))+
            uint16(int(left*1000.0))+
            uint16(int(right*1000.0))
        )
        
    def aux(self,channel,src):
        self.ac.sendCmd("CAuS",[1,channel,src>>8,src&0xFF])
    def audioSettings(self,src,option=None,volume=None,balance=None):
        mask = 0
        if option is None:
            option = 0
        else:
            mask += 1
        if volume is None:
            volume = 0
        else:
            mask += 2
        if balance is None:
            balance = 0
        else:
            mask += 4
        self.ac.sendCmd("CAMI",[mask,0]+uint16(src)+[option,0]+uint16(volume)+int16(balance)+[0,0])
    def audioMaster(self,volume):
        self.ac.sendCmd("CAMM",[1,0]+uint16(volume)+[0,0,0,0])
        
    def keyLuma(self,premulti=None,clip=None,gain=None,invert=None,me=0,keyer=0):
        mask = 0
        if premulti is not None: mask += 1
        if clip is not None: mask += 2
        else: clip=0
        if gain is not None: mask += 4
        else: gain=0
        if invert is not None: mask += 8
        clip = int(clip*10)
        gain = int(gain*10)
        
        self.ac.sendCmd("CKLm",[
            mask,
            me,keyer,
            1 if premulti else 0,
            clip>>8,clip&0xFF,
            gain>>8,gain&0xFF,
            1 if invert else 0,
            0,0,0
        ])
    def transSettings(self,style=None,me=0,trans=None):
        # Style:
        #  0 - Mix
        #  1 - Dip
        #  2 - Wipe
        #  3 - DVE
        #  4 - Sting
        # Trans:
        # bit 0 - bg
        # bit 1-4 - key1-4
        mask = 0
        if style is None:
            style = 0
        else:
            mask += 1
        if trans is None:
            trans = 0
        else:
            mask += 2
        self.ac.sendCmd("CTTp",[mask,me,style,trans])
    def mixSettings(self,rate,me=0):
        self.ac.sendCmd("CTMx",[int(me),int(rate),0,0])
    def wipeSettings(self,rate=None,pattern=None, width=None, fillsrc=None,
                symetry=None, softness=None, posx=None, posy=None,
                reverse=None, flipflop=None,me=0):
        mask = 0
        if rate is None:
            rate = 0
        else:
            mask += 1
        if pattern is None:
            pattern = 0
        else:
            mask += 2
        if width is None:
            width = 0
        else:
            mask += 4
        if fillsrc is None:
            fillsrc = 0
        else:
            mask += 8
        if symetry is None:
            symetry = 0
        else:
            mask += 16
        if softness is None:
            softness = 0
        else:
            mask += 32
        if posx is None:
            posx = 0
        else:
            mask += 64
        if posy is None:
            posy = 0
        else:
            mask += 128
        if reverse is None:
            reverse = 0
        else:
            mask += 256
        if flipflop is None:
            flipflop = 0
        else:
            mask += 512
        self.ac.sendCmd("CTWp",uint16(mask)+[me,rate,pattern,0]+
            uint16(width)+
            uint16(fillsrc)+
            uint16(symetry)+
            uint16(softness)+
            uint16(posx)+
            uint16(posy)+
            [reverse,flipflop]
            )
    def mediaSource(self,player,still=None,clip=None):
        type = 0
        mask = 1
        if still is None:
            still = 0
        else:
            mask += 2
            type = 1
        if clip is None:
            clip = 0
        else:
            mask += 4
            type = 2
        self.ac.sendCmd("MPSS",[mask,player,type,still,clip,0,0,0])
    def cut(self,me=0):
        self.ac.sendCmd("DCut",[me,0,0,0])
    def auto(self,me=0):
        self.ac.sendCmd("DAut",[me,0,0,0])
    def multiViewInput(self, mviewer, window, source):
        self.ac.sendCmd("CMvI",[mviewer,window]+uint16(source))
    def ssource(self, bg=None):
        masker = MaskDefault()
        bg = masker.getValueOrZero(bg, 1)
        key=0
        fore=0
        premulti=0
        clip=0
        gain=0
        invkey=0
        borderena=0
        borderbevel=0
        outwidth=0
        inwidth=0
        outsoft=0
        insoft=0
        bevsoft=0
        bevpos=0
        borderhue=0
        bordersat=0
        borderluma=0
        lightdir=0
        lightalt=0
        mask = masker.mask
        self.ac.sendCmd("CSSc", 
                uint32(mask)
                + uint16(bg)
                + uint16(key)
                + [fore,premulti]
                + uint16(clip)
                + uint16(gain)
                + [invkey,borderena,borderbevel,0]
                + uint16(outwidth)
                + uint16(inwidth)
                + [outsoft, insoft, bevsoft, bevpos]
                + uint16(borderhue)
                + uint16(bordersat)
                + uint16(borderluma)
                + uint16(lightdir)
                + [lightalt,0]

                )
    def boxsrc(self, boxnum, enable=None, src=None, 
            x=None, y=None, size=None, 
            cropped=None, 
            top=None, bottom=None, 
            left=None, right=None):
        masker = MaskDefault()
        # 0 1 2 3  4  5  6   7   8   9
        # 1 2 4 8 16 32 64 128 256 512
        # print mask, enable, src
        enable = masker.getValueOrZero(enable, 1)
        src = masker.getValueOrZero(src, 2)
        x = masker.getValueOrZero(x, 4)
        y = masker.getValueOrZero(y, 8)
        size = masker.getValueOrZero(size, 16)
        cropped = masker.getValueOrZero(cropped, 32)
        top = masker.getValueOrZero(top, 64)
        bottom = masker.getValueOrZero(bottom, 128)
        left = masker.getValueOrZero(left, 256)
        right = masker.getValueOrZero(right, 512)
        mask = masker.mask
        self.ac.sendCmd("CSBP",
                  uint16(mask)
                + [boxnum-1, enable]
                + uint16(src)
                + int16(x)
                + int16(y)
                + uint16(size)
                + [cropped,0]
                + uint16(top)
                + uint16(bottom)
                + uint16(left)
                + uint16(right)
                + [0, 0]
                )
    def parseCmd(self, cmd, args):
        if cmd == "_VMC":
            pass
            #self.cb("videomodes", dict(modes = unpack("!I",args)))
        elif cmd == "VidM":
            videoformat = unpack("B",args[0])[0]
            self.videoformat = videomodes[videoformat]
            self.cb("videoformat",dict(key=videoformat,format=self.videoformat))
        elif cmd == "PrgI":
            self.cb("program",dict(
                me = ord(args[0]),
                src = unpack("!H",args[2:4])[0]
            ))
        elif cmd == "PrvI":
            self.cb("preview",dict(
                me = ord(args[0]),
                src = unpack("!H",args[2:4])[0]
            ))
        elif cmd == "KeOn":
            self.cb("key",dict(
                me = ord(args[0]),
                keyer = ord(args[1]),
                enabled = ord(args[2]),
            ))
        elif cmd == "KeBP":
            self.cb("keyinfo",dict(
                me = ord(args[0]),
                keyer = ord(args[1]),
                keytype = ord(args[2]),
                keyenabled = True if ord(args[3]) else False,
                flyenabled = True if ord(args[5]) else False,
                fillsrc = unpack("!H",args[6:8])[0],
                keysrc = unpack("!H",args[8:10])[0],
                masked = True if ord(args[10]) else False,
                top = unpack("!h",args[12:14])[0]/1000.0,
                bottom = unpack("!h",args[14:16])[0]/1000.0,
                left = unpack("!h",args[16:18])[0]/1000.0,
                right = unpack("!h",args[18:20])[0]/1000.0
            ))
        elif cmd == "KeLm":
            self.cb("keyluma",dict(
                me = ord(args[0]),
                keyer = ord(args[1]),
                premulti = ord(args[2]),
                clip = unpack("!H",args[4:6])[0]/10.0,
                gain = unpack("!H",args[6:8])[0]/10.0,
                invert = ord(args[8]),
            ))
        elif cmd == "DskB":
            self.cb("dsksources",dict(
                keyer = ord(args[0]),
                fillsrc = unpack("!H",args[2:4])[0],
                keysrc = unpack("!H",args[4:6])[0],
            ))
        elif cmd == "DskP":
            self.cb("dsksetting",dict(
                keyer = ord(args[0]),
                tie = ord(args[1]),
                rate = ord(args[2]),
                premulti = ord(args[3]),
                clip = unpack("!H",args[4:6])[0]/10.0,
                gain = unpack("!H",args[6:8])[0]/10.0,
                invert = ord(args[8]),
                masked = ord(args[9]),
                top = unpack("!h",args[10:12])[0]/1000.0,
                bottom = unpack("!h",args[12:14])[0]/1000.0,
                left = unpack("!h",args[14:16])[0]/1000.0,
                right = unpack("!h",args[16:18])[0]/1000.0,
            ))
        elif cmd == "DskS":
            self.cb("dsk",dict(
                keyer = ord(args[0]),
                onair = ord(args[1]),
                trans = ord(args[2]),
                auto = ord(args[3]),
                frames = ord(args[4]),
            ))
        elif cmd == "FtbS":
            self.cb("black",dict(
                me = ord(args[0]),
                black = ord(args[1]),
                trans = ord(args[2]),
                frames = ord(args[3]),
            ))
        elif cmd == "ColV":
            self.cb("color",dict(
                generator = ord(args[0]),
                src = unpack("!H",args[2:4])[0],
            ))
        elif cmd == "AuxS":
            """
            self.cb("aux",dict(
                channel = ord(args[0]),
                hue = unpack("!H",args[2:4])[0]/10.0,
                saturation = unpack("!H",args[4:6])[0]/10.0,
                luma = unpack("!H",args[6:8])[0]/10.0,
            ))
            """
        elif cmd == "AMIP":
            self.cb("audio",dict(
                src = unpack("!H",args[0:2])[0],
                type = ord(args[2]),
                mediaplayer = True if ord(args[6]) else False,
                plug = ord(args[7]),
                mix = ord(args[8]),
                volume = unpack("!H",args[10:12])[0],
                balance = unpack("!h",args[12:14])[0]
            ))
        elif cmd == "AMMO":
            self.cb("audiomaster",dict(
                volume = unpack("!H",args[0:2])[0]
            ))
        elif cmd == "AMmO":
            self.cb("audiomonitor",dict(
                enabled = True if ord(args[0]) else False,
                volume = unpack("!H",args[2:4])[0],
                mute = True if ord(args[4]) else False,
                solo = True if ord(args[5]) else False,
                src = unpack("!H",args[6:8])[0],
                dim = True if ord(args[8]) else False,
            ))
        elif cmd == "TlSr":
            sources = []
            nosources = unpack("!H",args[0:2])[0]
            for i in range(nosources):
                sources.append(dict(
                    src = unpack("!H",args[2+(i*3):4+(i*3)])[0],
                    dim = True if ord(args[4+(i*3)]) else False,
                ))
            self.cb("tally",dict(
                sources = sources
            ))
        elif cmd == "Warn":
            text = args.split("\x00",1)[0]
            self.cb("WARNING",text)
        elif cmd == "InPr":
            src = unpack("!H",args[0:2])[0]
            name = args[2:22].split("\x00",1)[0]
            short = args[22:26].split("\x00",1)[0]
            self.srcNames[name] = src
            self.srcNames[short] = src
        # Internal commands
        elif cmd in ["connect","disconnect","timeout"]:
            self.cb(cmd,{})
        # Unimplemented commands
        elif cmd in (
                # Variables
                "_ver","_pin","_top","_MeC","_mpl","_MvC","_SSC","_TlC","_AMC","_MAC",

                # Status commands
                "Powr","DcOt","InPr","MvPr","MvIn","TrSS","TrPr",
                "TrPs","TMxP","TDpP","TWpP","TDvP","TStP","KeCk","KePt",
                "KeDV","KeFS","KKFP","FtbP","CCdo","CCdP","RCPS",
                "MPCE","MPSp","MPCS","MPAS","MPfe","MRPr","MPrp","MRcS",
                "SSrc","SSBP","AMLv","AMTl","Time","TlIn",

                # Unknown commands
                "LKST","InCm","FTDC","CCst","MvVM",
                ):
            pass
            print "Unhandled",cmd,str2hex(args)
            #print "Unhandled",cmd,repr(args)
        else:
            print "Unknown command:",cmd,str2hex(args)

if __name__ == "__main__":
    # Manual tests
    def cb(cmd,args):
        print repr(cmd),repr(args)
    #atem = AtemDevice("10.20.126.242",callback=cb)
    atem = AtemDevice(sys.argv[1],callback=cb)
    #atem = AtemDevice("10.21.89.12",callback=cb)
    while 1:
        cmd = raw_input().strip()
        if cmd == "1":
            atem.program(1)
        elif cmd == "2":
            atem.program(2)
        elif cmd == "p1":
            atem.preview(1)
        elif cmd == "p2":
            atem.preview(2)
        elif cmd == "l":
            atem.keyType(0)
        elif cmd == "c":
            atem.keyType(1)
        elif cmd == "l1":
            atem.keyLuma(False,47.9,70.0,False)
        elif cmd == "l2":
            atem.keyLuma(False,62.1,20.2,False)
        elif cmd == "l3":
            atem.keyLuma(True,62.1,20.2,False)
        elif cmd == "l4":
            atem.keyLuma(invert=True)
        elif cmd == "d0":
            atem.dskOn(1,False)
        elif cmd == "d1":
            atem.dskOn(1,True)
        elif cmd == "dp0":
            atem.dskLuma(1,premulti=False)
        elif cmd == "dp1":
            atem.dskLuma(1,premulti=True)
        elif cmd == "k0":
            atem.keyOn(False)
        elif cmd == "k1":
            atem.keyOn(True)
        elif cmd == "a1":
            atem.aux(0,1)
        elif cmd == "a2":
            atem.aux(0,2)
        elif cmd == "m1":
            atem.mediaSource(0,still=0)
        elif cmd == "m2":
            atem.mediaSource(0,still=1)
        elif cmd == "c":
            atem.cut()
        elif cmd == "a":
            atem.auto()
        elif cmd[0] == "v":
            atem.audioSettings(int(cmd[1]),volume=int(cmd[2])*10000)
        elif cmd[0] == "m":
            atem.audioMaster(int(cmd[1])*10000)
        elif cmd == "con":
            atem.reconnect()
        elif cmd[0] == "b":
            atem.boxsrc(int(cmd[1]),src=int(cmd[2:]),enable=1)
        elif cmd[0] == "s":
            atem.ssource(int(cmd[1:]))

