##
## unfinished!
##
ALWAYS_HIDAPI = False

from collections import namedtuple
import struct
import re
import os
import hashlib
import time
import math
from wiimote_constants import *
from threading import Thread

JOYCON_VID = 0x057E
JOYCON_PIDS = [0x2007,]
NEUTRAL_RUMBLE = b'\x00\x01\x40\x40\x00\x01\x40\x40'
IR_NONE       = -1
IR_POINTING   = 4
IR_CLUSTERING = 6
IR_IMAGE      = 7

_IR_FRAGMENT_SIZE = 300

if os.name == 'nt':
    USE_HID = True
    from windows.wiipair import pair_joycon
else:
    USE_HID = ALWAYS_HIDAPI 
    from linux.wiimote_scan import scan_wiimote_dbus_poll

if USE_HID:
    import hid
else:
    import socket

openedDevices = set()

DEFAULT_IR_LEVEL = 5

crc8_table = [
    0x00, 0x07, 0x0E, 0x09, 0x1C, 0x1B, 0x12, 0x15, 0x38, 0x3F, 0x36, 0x31, 0x24, 0x23, 0x2A, 0x2D,
    0x70, 0x77, 0x7E, 0x79, 0x6C, 0x6B, 0x62, 0x65, 0x48, 0x4F, 0x46, 0x41, 0x54, 0x53, 0x5A, 0x5D,
    0xE0, 0xE7, 0xEE, 0xE9, 0xFC, 0xFB, 0xF2, 0xF5, 0xD8, 0xDF, 0xD6, 0xD1, 0xC4, 0xC3, 0xCA, 0xCD,
    0x90, 0x97, 0x9E, 0x99, 0x8C, 0x8B, 0x82, 0x85, 0xA8, 0xAF, 0xA6, 0xA1, 0xB4, 0xB3, 0xBA, 0xBD,
    0xC7, 0xC0, 0xC9, 0xCE, 0xDB, 0xDC, 0xD5, 0xD2, 0xFF, 0xF8, 0xF1, 0xF6, 0xE3, 0xE4, 0xED, 0xEA,
    0xB7, 0xB0, 0xB9, 0xBE, 0xAB, 0xAC, 0xA5, 0xA2, 0x8F, 0x88, 0x81, 0x86, 0x93, 0x94, 0x9D, 0x9A,
    0x27, 0x20, 0x29, 0x2E, 0x3B, 0x3C, 0x35, 0x32, 0x1F, 0x18, 0x11, 0x16, 0x03, 0x04, 0x0D, 0x0A,
    0x57, 0x50, 0x59, 0x5E, 0x4B, 0x4C, 0x45, 0x42, 0x6F, 0x68, 0x61, 0x66, 0x73, 0x74, 0x7D, 0x7A,
    0x89, 0x8E, 0x87, 0x80, 0x95, 0x92, 0x9B, 0x9C, 0xB1, 0xB6, 0xBF, 0xB8, 0xAD, 0xAA, 0xA3, 0xA4,
    0xF9, 0xFE, 0xF7, 0xF0, 0xE5, 0xE2, 0xEB, 0xEC, 0xC1, 0xC6, 0xCF, 0xC8, 0xDD, 0xDA, 0xD3, 0xD4,
    0x69, 0x6E, 0x67, 0x60, 0x75, 0x72, 0x7B, 0x7C, 0x51, 0x56, 0x5F, 0x58, 0x4D, 0x4A, 0x43, 0x44,
    0x19, 0x1E, 0x17, 0x10, 0x05, 0x02, 0x0B, 0x0C, 0x21, 0x26, 0x2F, 0x28, 0x3D, 0x3A, 0x33, 0x34,
    0x4E, 0x49, 0x40, 0x47, 0x52, 0x55, 0x5C, 0x5B, 0x76, 0x71, 0x78, 0x7F, 0x6A, 0x6D, 0x64, 0x63,
    0x3E, 0x39, 0x30, 0x37, 0x22, 0x25, 0x2C, 0x2B, 0x06, 0x01, 0x08, 0x0F, 0x1A, 0x1D, 0x14, 0x13,
    0xAE, 0xA9, 0xA0, 0xA7, 0xB2, 0xB5, 0xBC, 0xBB, 0x96, 0x91, 0x98, 0x9F, 0x8A, 0x8D, 0x84, 0x83,
    0xDE, 0xD9, 0xD0, 0xD7, 0xC2, 0xC5, 0xCC, 0xCB, 0xE6, 0xE1, 0xE8, 0xEF, 0xFA, 0xFD, 0xF4, 0xF3
]
    
def crc8(data, start, length):
    crc8 = 0
    for i in range(length):
        crc8 = crc8_table[crc8^(0xFF & data[start+i])]
    return crc8

def set_ir_sensitivity(s):
    DEFAULT_IR_LEVEL = s

def parseIRCalibration(data):
    if len(data) < 11:
        return None
    s = (0x55 + sum(data[i] & 0xFF for i in range(10))) & 0xFF
    if s != (data[10] & 0xFF):
        return None
    def getCoordinate(bits07_offset,bits89_offset,bits89_shift):
        return (data[bits07_offset] & 0xFF) | (((data[bits89_offset] >> bits89_shift) & 0x3) << 8)    
    
    irc = [ (getCoordinate(*icl[0]), getCoordinate(*icl[1])) for icl in IR_CALIBRATION_LOCATIONS ]
    
    def find(x,y):
        def cmp(a,b,d): 
            if not d:
                return a<b
            else:
                return b<a
        for i in range(4):
            if cmp(irc[i][0],512,x) and cmp(irc[i][1],384,y):
                return irc[i]
        raise RuntimeError()
    try:
        # sort counterclockwise from lower left
        return [ find(0,0), find(1,0), find(1,1), find(0,1) ]
    except RuntimeError:
        return None
        
def getSWordLE(data, offset):
    x = (data[offset+1] & 0xFF) << 8 | (data[offset] & 0xFF)
    
    if x & 0x8000:
        return -((-x)&0xFFFF)
    else:
        return x
    
def getWordLE(data, offset):
    return (data[offset+1] & 0xFF) << 8 | (data[offset] & 0xFF)
    
def macStrip(mac):
    return re.sub(r'[^A-F0-9]','',mac.upper())
    
def macClean(mac):
    mac = macStrip(mac)
    if len(mac) != 12:
        return None
    return ":".join((mac[i:i+2] for i in range(0,12,2)))
    
class IRRegisters:
    LED_FLASHLIGHT = 0b01
    LED_STROBE = 0b10000000
    LED_12_OFF = 0b010000 ## TODO: check
    LED_34_OFF = 0b100000 ## TODO: check
    fields = ('resolution', 'exposure', 'maxExposure', 'leds', 'digitalGain',
                        'externalLightFilter', 'brightnessThreshold', 'leds12Intensity', 'leds34Intensity',
                        'flip', 'denoise', 'smoothingThreshold', 'interpolationThreshold', 'updateTime',
                        'pointingThreshold')
    
    def __init__(self, mode):
        for arg in IRRegisters.fields:
            setattr(self,arg,None)
        self.defaults(mode)
                
    def __repr__(self):
        return ", ".join(f+"="+repr(getattr(self,f)) for f in IRRegisters.fields)

    def defaults(self, mode):
        self.custom = []
        if mode == IR_CLUSTERING:
            self.resolution=320
            self.exposure=200
            self.maxExposure=0
            #self.leds=0
            self.leds = IRRegisters.LED_12_OFF | IRRegisters.LED_34_OFF #IRRegisters.LED_12_OFF | IRRegisters.LED_34_OFF
            self.digitalGain=1
            self.externalLightFilter=1
            self.brightnessThreshold=200
            #self.leds12Intensity=13
            #self.leds34Intensity=13
            self.leds12Intensity = 0x0
            self.leds34Intensity = 0x0
            self.flip=2
            self.denoise=1
            self.smoothingThreshold=35
            self.interpolationThreshold=68
            self.updateTime=50
            self.pointingThreshold=0
        elif mode == IR_POINTING:
            self.resolution=320
            self.exposure=200
            self.maxExposure=0
            #self.leds=0
            self.leds = IRRegisters.LED_12_OFF | IRRegisters.LED_34_OFF #IRRegisters.LED_12_OFF | IRRegisters.LED_34_OFF
            #self.digitalGain=16
            self.digitalGain=18
            self.externalLightFilter=0
            self.brightnessThreshold=200
            #self.leds12Intensity=13
            #self.leds34Intensity=13
            self.leds12Intensity = 0x0
            self.leds34Intensity = 0x0
            self.flip=2
            self.denoise=0
            self.smoothingThreshold=35
            self.interpolationThreshold=68
            self.updateTime=50
            #self.pointingThreshold=1
            self.pointingThreshold=0
            self.addCustom(0x00,0x24,0x0)
        elif mode == IR_IMAGE:
            self.resolution=320
            self.exposure=200
            self.maxExposure=0
            self.leds=0 # IRRegisters.LED_FLASHLIGHT
            self.digitalGain=16
            self.externalLightFilter=0
            self.brightnessThreshold=200
            self.leds12Intensity=13
            self.leds34Intensity=13
            self.flip=0
            self.denoise=0
            self.smoothingThreshold=35
            self.interpolationThreshold=68
            #self.updateTime=50
            self.pointingThreshold=1
            
    def clearCustom(self):
        self.custom = []
        
    def addCustom(self, page, register, value):
        self.custom.append( (page,register,value) )
    
    def read(self, j):
        page0 = j.get_mcu_registers(0x00)
        page1 = j.get_mcu_registers(0x01)
        r = page0[0x2e]
        if r == 0b00000000:
            self.resolution = 320
        elif r == 0b01010000:
            self.resolution = 160
        elif r == 0b01100100:
            self.resolution = 80
        elif r == 0b01101001:
            self.resolution = 40
        else:
            self.resolution = -(r & 0xFF)
        e = (page1[0x30] & 0xFF) | ((page1[0x31] & 0xFF)<<8)
        self.exposure = (e * 1000 + 31200//2) // 31200
        self.maxExposure = page1[0x32]
        self.leds = page0[0x10]
        self.digitalGain = ((page1[0x2e] & 0xFF) | ((page1[0x2f] & 0xFF)<<8)) >> 4
        self.externalLightFilter = 1 if page0[0x0e] else 3
        self.brightnessThreshold = page1[0x43]
        self.leds12Intensity = page0[0x11]
        self.leds34Intensity = page0[0x12]
        self.flip = page0[0x2d]
        self.denoise = page1[0x67]
        self.smoothingThreshold = page1[0x68]
        self.interpolationThreshold = page1[0x69]
        self.updateTime = page0[0x04]
        self.pointingThreshold = page1[0x21]
    
    def write(self, j):
        data = []
        if self.resolution is not None:
            if self.resolution == 320:
                r = 0b00000000
            elif self.resolution == 160:
                r = 0b01010000
            elif self.resolution == 80:
                r = 0b01100100
            elif self.resolution == 40:
                r = 0b01101001
            else:
                r = -self.resolution
            data.append((0x00,0x2e,r))
        if self.exposure is not None:
            e = (31200 * self.exposure + 500) // 1000
            data.append((0x01,0x30,e & 0xFF))
            data.append((0x01,0x31,(e>>8) & 0xFF))
        if self.maxExposure is not None:
            data.append((0x01,0x32,1 if self.maxExposure else 0))
        if self.leds is not None:
            data.append((0x00,0x10,self.leds))
        if self.digitalGain is not None:
            data.append((0x01,0x2e,(self.digitalGain & 0xF)<<4))
            data.append((0x01,0x2f,(self.digitalGain & 0xF0)>>4))
        if self.externalLightFilter is not None:
            data.append((0x00,0x0e,3 if self.externalLightFilter else 0))
        if self.brightnessThreshold is not None:
            data.append((0x01,0x43,self.brightnessThreshold))
        if self.leds12Intensity is not None:
            data.append((0x00,0x11,self.leds12Intensity))
        if self.leds34Intensity is not None:
            data.append((0x00,0x12,self.leds34Intensity))
        if self.flip is not None:
            data.append((0x00,0x2d,self.flip))
        if self.denoise is not None:
            data.append((0x01,0x67,1 if self.denoise else 0))
        if self.smoothingThreshold is not None:
            data.append((0x01,0x68,self.smoothingThreshold))
        if self.interpolationThreshold is not None:
            data.append((0x01,0x69,self.interpolationThreshold))
        if self.updateTime is not None:
            data.append((0x00,0x04,self.updateTime))
        elif self.resolution is not None:
            data.append((0x00,0x04,0x02d if self.resolution == 40 else 0x32))
        if self.pointingThreshold is not None:
            data.append((0x01,0x21,self.pointingThreshold))
        for triple in self.custom:
            data.append(triple)
        while len(data):
            if len(data)<9:
                j.set_mcu_registers(data+[(0x00,0x07,0x01),])
                data = []
            else:
                j.set_mcu_registers(data[0:9])
                if len(data) == 9:
                    j.set_mcu_registers([(0x00,0x07,0x01),])
                data = data[9:]

class JoyCon:
    def __init__(self, timeout=5, connectTimeout=15, connectCallback=None, pair=True):
        self.connectCallback = connectCallback if connectCallback is not None else lambda msg: None
        self.timeout = timeout
        self.timeout_ms = int(timeout * 1000)
        self.connectTimeout = connectTimeout
        self.id = None
        self.state = {}
        self.accel0gCalibration = (512,512,512)
        self.accel1gCalibration = (616,616,616)
        self.irCalibration = [(127,93),(896,93),(896,674),(127,674)]
        self.zeroBalanceBoardOnButton = True
        self.rpt_mode = RPT_IR|RPT_BTN|RPT_ACC # |RPT_EXT
        self.mesg_callback = lambda data,t: None
        self.name = None
        self.prevButtons = 0
        self._rumble = 0
        self.ir_mode = IR_NONE
        self.ir_registers = None
        
        if USE_HID:
            self.initHID(connectTimeout=connectTimeout+5,pair=pair)
        else:
            self.initSocket(pair=pair)

        self.opened = True
        self.rumble = False
        #self.led = 0x60
        self.packet_counter = 0
        print("calibrate")
        self.calibrate()
        
        if self.id is None:
            self.id = "joycon"
        #self.led = 0
        
    def initSocket(self,pair=True):
        if pair:
            self.connectCallback(CONNECT_PRESS_12)
        mac,name = scan_wiimote_dbus_poll(timeout=self.connectTimeout,blacklist=openedDevices)
        if not mac:
            raise RuntimeError()
        self.s_control = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.s_interrupt = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)        
        self.s_control.settimeout(self.connectTimeout)
        self.s_control.connect((mac, PSM_CONTROL))
        self.s_interrupt.settimeout(self.connectTimeout)
        self.s_interrupt.connect((mac, PSM_INTERRUPT))
        self.s_control.settimeout(self.timeout)
        self.s_interrupt.settimeout(self.timeout)
        self.id = mac
        self.path = mac
        openedDevices.add(mac)
        
    def close(self):
        if self.listening:
            self.listening = False
            try:
                self.send(bytes((0x13, 0x00)))
                time.sleep(0.05)
                self.send(bytes((0x1A, 0x00)))
                time.sleep(0.05)
            except:
                pass
            
        self.opened = False
        openedDevices.discard(self.path)
            
        if USE_HID:
            try:
                self.handle.close()
            except:
                pass
        else:
            try:
                self.s_control.close()
            except:
                pass
            try:
                self.s_interrupt.close()
            except:
                pass
                
    def getSerial(self,dev):
        if 'serial_number' in dev and dev['serial_number']:
            return dev['serial_number']
        handle = hid.device()
        try:
            handle.open_path(dev['path'])
            return handle.get_serial_number_string()
        except:
            return "wiimote"
        finally:
            handle.close()
            
    def openJoyCon(self,mac=None):
        for dev in hid.enumerate():
            if dev['vendor_id'] == JOYCON_VID and dev['product_id'] in JOYCON_PIDS:
                if mac is not None:
                    if macStrip(mac) != macStrip(getSerial(dev)):
                        continue
                path = dev['path']
                if path in openedDevices:
                    continue
                handle = hid.device()
                try:
                    handle.open_path(path)
                except:
                    continue
                try:
                    handle.set_nonblocking(False)
                    # status request 
                    self.id = macClean(handle.get_serial_number_string())
                    print("id",self.id)
                except:
                    handle.close()
                    continue
                    
                print(f"Found JoyCon at: {path}")
                self.path = path
                openedDevices.add(path)
                return handle
        return None       

    def initHID(self,connectTimeout=15,pair=True):
        if os.name == "nt":
            self.connectCallback(CONNECT_QUICK)
            self.handle = self.openJoyCon()
        else:
            self.handle = None
        if not self.handle:
            mac = None
            if os.name == "nt":
                if pair:
                    pair_joycon(timeout=connectTimeout,connectCallback=self.connectCallback)
            else:
                if pair:
                    self.connectCallback(CONNECT_PRESS_12)
                    mac,_ = scan_wiimote_dbus_poll(timeout=self.connectTimeout,blacklist=openedDevices,connectAndPair=True)
                    if not mac:
                        print("Cannot find Wiimote")
                        raise RuntimeError()
            t = time.monotonic()
            while not self.handle and time.monotonic() < t + self.timeout:
                self.handle = self.openJoyCon(mac=mac)
                if not self.handle:
                    time.sleep(0.1)
            if not self.handle:
                print("Failed to connect")
                raise RuntimeError()
        
    def recv(self,size):
        if not self.opened:
            return None
        try:
            if USE_HID:
                data = self.handle.read(size,timeout_ms=self.timeout_ms)
                if not data:
                    raise OSError()
                return data
            else:
                data = self.s_interrupt.recv(size+1)
                if not data or data[0] & 0xFF != 0xA1:
                    raise OSError()
                return data[1:]
        except OSError:
            self.close()
            return None
            
    def send(self,out):
        if not self.opened:
            return None
        try:
            if USE_HID:
                self.handle.write(bytes(out))
            else:
                self.s_interrupt.send(bytes((0xA2,)) + bytes(out))
        except OSError:
            raise Exception()
            self.close()

    def send_control(self,out,crcLocation=None,crcStart=None,crcLength=None,confirm=None,command=0x01,confirmRetries=16):
        if not self.opened:
            raise IOError()
            
        r = confirmRetries
        while r>0:
            data = bytearray((command,self.packet_counter))+NEUTRAL_RUMBLE+bytes(out)
            if len(data)>49:
                data = data[:49]
            elif len(data)<49:
                data += bytes((0,))*(49-len(data))
            if crcLocation is not None:
                data[crcLocation] = crc8(data, crcStart, crcLength)

            try:
                if USE_HID:
                    self.handle.write(data)
                else:
                    self.s_control.send(data)
            except IOError:
                self.close()
                raise IOError()
            self.packet_counter = (self.packet_counter+1) & 0xF

            if confirm is None:
                return None
                
            r2 = 6
            while r2 > 0:
                report = self.recv(512)
                haveRightReportType = None
                for pos,value in confirm:
                    if pos == 0 and len(report) >= 1 and report[0] == value:
                        haveRightReportType = True
                    elif len(report)<=pos or report[pos] != value:
                        break
                else:
                    return report
                    
                if haveRightReportType:
                    break
                else:
                    r2 -= 1
            r -= 1
        raise IOError("not confirmed")
            
    def _set_report_type(self, reportType):
        self._report_type = reportType
        self.send_control(b'\x03'+bytes((reportType,)), confirm=((0xD,0x80),(0xE,0x3)))

    def get_mcu_registers(self,page):
        cmd = bytes((0x03,0x01,page,0x00,0x7f))
        report = self.send_control(b'\x03'+cmd,crcLocation=47,crcStart=11,crcLength=36,
                    confirm=((49,0x1b),(51,page),(52,0x00)),command=0x11)
        if not report:
            raise IOError("Cannot read MCU registers")
        else:
            return tuple(report[54+i] for i in range(report[52]+report[53]))

    def set_mcu_registers(self, registers):
        count = len(registers)
        if count > 9:
            raise ValueError("Too many registers")
        cmd = bytes((0x23,0x04,count,))
        for page,reg,value in registers:
            cmd += bytes((page,reg,value))
        if count < 9:
            cmd += bytes((0,0,0)) * (9-count)
        self.send_control(b'\x21'+cmd, crcLocation=48, crcStart=12, crcLength=36, confirm=((0,0x21),(14,0x21)))
        #time.sleep(0.015)
        return True

    def _request_ir_report(self,fragmentAcknowledge=0,ignore=False):
        self.send_control(b'\x03\x00\x00\x00'+bytes((fragmentAcknowledge,))+(b'\x00'*33)+b'\xFF', command=0x11, crcLocation=47, crcStart=11, crcLength=36, confirm=((0,0x31),) if ignore else None)

    def set_ir_mode(self,ir_mode,ir_registers=None):
        self.ir_mode = IR_NONE if ir_mode is None else ir_mode
        self.ir_registers = ir_registers

    def _set_reporting(self):
        if self.rpt_mode & RPT_ACC:
            self.send_control(b'\x40\x01') # turn on accel sensors
            
        if self.rpt_mode & RPT_IR:
            if self.ir_mode == IR_NONE:
                self.ir_mode = IR_POINTING
                self.ir_registers = None
            if self.ir_registers is None:
                self.ir_registers = IRRegisters(self.ir_mode)                
            self._set_report_type(0x31)
            self.send_control(b'\x22\x01', confirm=((0xD,0x80),(0xE,0x22)))
            self.send_control(b'\x01', confirm=((0,0x31),(49,0x01),(56,0x01)), command=0x11)
            self.send_control(b'\x21\x01\x00\x05', crcLocation=48, crcStart=12, crcLength=36, confirm=((0,0x21),  )) # (15,0x01),(22, 0x01)
            self.send_control(b'\x01', confirm=((0,0x31),(49,0x01),(56,0x05)), command=0x11)
            args = struct.pack('<BBBBHH', 0x23, 0x01, self.ir_mode, 1, 0x0500, 0x1800)
            self.send_control(b'\x21'+args, crcLocation=48, crcStart=12, crcLength=36)

            if self.ir_registers is not None:
                self.ir_registers.write(self)
            
            for retries in range(500):
                self._request_ir_report()
                report = self.recv(512)
                if self._have_ir_data(report):
                    break
            else:
                raise IOError("No IR data received")
            
            if self.ir_registers is not None:
                self.ir_registers.write(self)
            return 362
        else:
            self._set_report_type(0x30)
            self.send_control(b'\x21\x23\x01\x02', crcLocation=48, crcStart=12, crcLength=36)
            self.send_control(b'\x22\x00')
            return 49
            
    @property
    def rumble(self):
        return self._rumble != 0
        
    @rumble.setter
    def rumble(self, x):
        self._rumble = 1 if x else 0
        #self.send((0x10,self._rumble)) # TODO
         
    @property
    def led(self):
        return self._leds
    
    @led.setter
    def led(self, l):
        #self.send((0x11,l | self._rumble))
        # todo
        self._leds = l
        
    def enable(self,mode=0,irLevel=DEFAULT_IR_LEVEL): # mode is ignored
        self.listening = True
        self.listenThread = Thread(target = self.listen, args=(irLevel,))
        self.listenThread.start()
        
    def _have_ir_data(self, report):
        return self.ir_mode is not None and report[0] == 0x31 and report[49] == 0x03 and report[51] == self.ir_mode
        
    def _get_ir_image(self):
        return self._ir_last_image

    def get_ir_cluster(self, data):
        brightness,pixels,cm_y_64,cm_x_64,y_start,y_end,x_start,x_end = struct.unpack("<HHHHHHHH", bytes(data))
        return namedtuple("ir_cluster", ["brightness", "pixels", "cm", "start", "end"])(
            brightness, pixels, (cm_x_64/64.,cm_y_64/64.), (x_start,y_start), (x_end,y_end));

    def _get_ir_clusters(self, report):
        if self.ir_mode == IR_POINTING or self.ir_mode == IR_CLUSTERING:
            clusters = []
            if self._have_ir_data(report):
                i = 61
                while i + 16 <= 59+300:
                    if self.ir_mode == IR_POINTING and (i == 61 + 48 or i == 61 + 97 or i == 61 + 146 or i == 61 + 195 or i == 61 + 244):
                        i += 1
                    if report[i] != 0 or report[i+1] !=0:
                        clusters.append(self.get_ir_cluster(report[i:i+16]))
                    i += 16
            return clusters
        else:
            return None

    def listen(self,irLevel):
        try:
            reportSize = self._set_reporting()

            while self.listening:
                data = self.recv(reportSize)
                if not self.listening:
                    break
                if not data:
                    time.sleep(0.01)
                    continue
                out = {}
                t = time.monotonic()
                if data[0] == 0x30 or data[0] == 0x31:
                    buttons = 0
                    btn_right_byte = data[3]
                    btn_shared_byte = data[4]
                    btn_left_byte = data[5]                
                    if btn_right_byte & 0x08:
                        buttons |= BTN_A
                    if btn_right_byte & 0x04:
                        buttons |= BTN_B
                    if btn_shared_byte & 0x02:
                        buttons |= BTN_PLUS
                    if btn_shared_byte & 0x10:
                        buttons |= BTN_HOME
        
    #        'X': bool(btn_right_byte & 0x02),
    #        'Y': bool(btn_right_byte & 0x01),
    #        'ZR': bool(btn_right_byte & 0x80),
    #        'R': bool(btn_right_byte & 0x40),
                    out["buttons"] = buttons

                    self.prevButtons = out["buttons"]
                    if self._have_ir_data(data):
                        ir_full = self._get_ir_clusters(data)
                        out["ir_full"] = ir_full
                        ir_short = [None,None,None,None]
                        for i in range(min(4,len(ir_full))):
                            d = ir_full[i]
                            ir_short[i] = ((d.cm[0]*(768./320.),d.cm[1]*(384./200.)),math.sqrt(d.pixels))
                        out["ir"] = ir_short
                        
                    if self.rpt_mode & RPT_ACC:
                        x,y,z = struct.unpack_from('<hhh', bytes(data),13+(2*12))
                        #out["acc_raw"] = (x,y,z)
                        out["acc_calib"] = ((x-self.accel0g[0])*self.accelScale[0], (y-self.accel0g[1])*self.accelScale[0], (z-self.accel0g[2])*self.accelScale[0] )
                        x,y,z = struct.unpack_from('<hhh', bytes(data),19+(2*12))
                        #out["gyro_raw"] = (x,y,z) 
                        out["gyro_calib"] = ((x-self.gyroOffset[0])*self.gyroScale[0], (y-self.gyroOffset[1])*self.gyroScale[0], (z-self.gyroOffset[2])*self.gyroScale[0] )
                    if self.ir_mode:
                        self._request_ir_report()
                    
                    self.state = out
                    self.mesg_callback(out,t)        
        except IOError as e:
            print(e)
            self.close()
            
    def read_flash(self,address,length):
        subCommand = b'\x10' + bytes( ( address & 0xFF, ( address >> 8) & 0xFF, ( address >> 16) & 0xFF, ( address >> 24) & 0xFF, length ) )
        confirm = [(0,0x21),(13,0x90)] 
        for i in range(len(subCommand)):
            confirm.append((14+i,subCommand[i]))
        report = self.send_control(subCommand, confirm=confirm,)
        return report[13+7:13+7+length]

    def calibrate(self):
        if self.read_flash(0x8026,2) == b'\xB2\xA1':
            cal = self.read_flash(0x8028, 24) # user data
        else:
            cal = self.read_flash(0x6020, 24) # factory data
        imuCal = []
        for i in range(12):
            imuCal.append(getSWordLE(cal,2*i))
        self.accel0g = (0,0,0) # imuCal[0:3]
        self.accelScale = tuple((x/(0x4000*4096)) for x in imuCal[3:6])
        self.gyroOffset = imuCal[6:9]
        self.gyroScale = tuple((x/(0x343b*4096)) for x in imuCal[9:12])

            
             
if __name__=='__main__':
    w = JoyCon(connectCallback=print)
    print(w.irCalibration)
    print(w.accel0gCalibration)
    print(w.accel1gCalibration)
    prevButtons = 0
    def callback(data,t):
        global prevButtons
        print(data)
        if (data['buttons'] & ~prevButtons) & BTN_A:
            w.rumble = True
        if (prevButtons & ~data['buttons']) & BTN_A:
            w.rumble = False
        prevButtons = data['buttons']            
        
    w.mesg_callback = print
    w.rpt_mode=RPT_IR|RPT_EXT|RPT_ACC|RPT_IR
    w.enable()
    print("running")
    while w.opened:
        time.sleep(1)
        pass
