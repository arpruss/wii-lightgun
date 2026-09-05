ALWAYS_HIDAPI = False
WINDOWS_USE_WiiPair_exe = False

import os
import hashlib
import time
from threading import Thread

if os.name == 'nt':
    USE_HID = True
    if WINDOWS_USE_WiiPair_exe:
        import subprocess
    else:
        #import windows.wiipair as wiipair
        from windows.wp import pair_wiimote
else:
    USE_HID = ALWAYS_HIDAPI 

if USE_HID:
    import hid
else:
    import linux.wiimote_scan as wiimote_scan
    import socket

WIIUSE = False
WIIMOTE_VID = 0x057e
WIIMOTE_PIDS = [0x0306, 0x0330]

PSM_CONTROL = 17
PSM_INTERRUPT = 19

RW_EEPROM = 0
RW_REG = 0x04

EVENT_DT = .01

NUNCHUK_BTN_Z = 0x01
NUNCHUK_BTN_C = 0x02
BTN_B = 0x04
BTN_A = 0x08
BTN_1 = 0x02
BTN_2 = 0x01
BTN_PLUS = 0x1000
BTN_MINUS = 0x0010
BTN_HOME = 0x0080
BTN_LEFT = 0x0100
BTN_RIGHT = 0x0200
BTN_DOWN = 0x0400
BTN_UP = 0x0800
LED1_ON = 0x10
LED2_ON = 0x20
LED3_ON = 0x40
LED4_ON = 0x80
RPT_IR =  1
RPT_BTN = 2
RPT_ACC = 4
RPT_EXT = 8
FLAG_MESG_IFC = 0
EXT_NONE = 0
EXT_NUNCHUK = 1

IR_CALIBRATION_LOCATIONS = ( ((0,2,4),(1,2,6)),  # X1,Y1
                             ((3,2,0),(4,2,2)),  # X2,Y2
                             ((5,7,4),(6,7,6)),  # X3,Y3
                             ((8,7,0),(9,7,2)) ) # X4,Y4 
                             
IR_LEVELS = ( (b"\x02\x00\x00\x71\x01\x00\x64\x00\xFE", b"\xFD\x05"),
              (b"\x02\x00\x00\x71\x01\x00\x96\x00\xB4", b"\xB3\x04"),
              (b"\x02\x00\x00\x71\x01\x00\xAA\x00\x64", b"\x63\x03"),
              (b"\x02\x00\x00\x71\x01\x00\xC8\x00\x36", b"\x35\x03"),
              (b"\x02\x00\x00\x71\x01\x00\x72\x00\x20", b"\x1F\x03") )

ACCEL_0G_CALIBRATION_LOCATIONS = ( (0,3,4), (1,3,2), (2,3,0) )
ACCEL_1G_CALIBRATION_LOCATIONS = ( (4,7,4), (5,7,2), (6,7,0) )

CALIBRATION_OFFSET = 0
IR_CALIBRATION_OFFSET_1 = 0
IR_CALIBRATION_OFFSET_2 = 11
IR_CALIBRATION_SIZE = 11
ACCEL_CALIBRATION_OFFSET = 2 * IR_CALIBRATION_SIZE
ACCEL_CALIBRATION_SIZE = 10
CALIBRATION_SIZE = 2 * IR_CALIBRATION_SIZE + ACCEL_CALIBRATION_SIZE
DEFAULT_IR_LEVEL = 5

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
 
def parseAccelCalibration(data):
    if len(data) < 10:
        return None
    s = (0x55 + sum(data[i] & 0xFF for i in range(9))) & 0xFF
    if s != (data[9] & 0xFF):
        return None
    def getCoordinate(bits29_offset,bits01_offset,bits01_shift):
        return ((data[bits29_offset] & 0xFF) << 2) | ((data[bits01_offset] >> bits01_shift) & 0x3)    
        
    accel0g = tuple( getCoordinate(*cl) for cl in ACCEL_0G_CALIBRATION_LOCATIONS )
    accel1g = tuple( getCoordinate(*cl) for cl in ACCEL_1G_CALIBRATION_LOCATIONS )
    
    return accel0g, accel1g

def getWord(data, offset):
    return (data[offset] & 0xFF) << 8 | (data[offset+1] & 0xFF)
    
def WiiPair(connectTimeout=15):
    if WINDOWS_USE_WiiPair_exe:
        print("Running WiiPair")
        try:
            subprocess.run([os.sep.join([os.path.dirname(os.path.realpath(__file__)),"windows","WiiPair.exe"])], capture_output=False, timeout=connectTimeout)
        except subprocess.TimeoutExpired:
            print("Failed")
            return False
        return True
    else:
        return wiipair.pair_wiimote(timeout=connectTimeout)
    
class Wiimote:
    def __init__(self, timeout=5, connectTimeout=15, connectCallback=None):
        self.connectCallback = connectCallback if connectCallback is not None else lambda msg: None
        self.timeout = timeout
        self.connectTimeout = connectTimeout
        self.address = None
        self.state = { 'buttons': 0, 'acc_raw': [512,512,616], 'acc_calib': [0.,0.,1.], 'ir': [None,None,None,None] }
        self.accel0gCalibration = [(512,512,512)]
        self.accel1gCalibration = [(616,616,616)]
        self.irCalibration = [(127,93),(896,93),(896,674),(127,674)]
        self.rpt_mode = RPT_IR|RPT_BTN|RPT_ACC#|RPT_EXT
        self.mesg_callback = lambda data,t: None
        self._rumble = 0
        
        if USE_HID:
            self.initHID(connectTimeout=connectTimeout+5)
        else:
            self.connectCallback("Press 1+2 on Wii Remote")
            self.initSocket()
        self.rumble = False
        self.led = 0x60
        self.send((0x12,0x04,0x30))
        if not self.calibrate():
            raise RuntimeError()
        self.led = 0xF0-0x60
        if self.address is None:
            self.address = "wiimote"
        
    def initSocket(self):
        mac = wiimote_scan.scan_wiimote_dbus_poll(timeout=self.connectTimeout)
        if not mac:
            raise RuntimeError()
        self.address = mac
        self.s_control = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.s_interrupt = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)        
        self.s_control.settimeout(self.connectTimeout)
        self.s_control.connect((self.address, PSM_CONTROL))
        self.s_interrupt.settimeout(self.connectTimeout)
        self.s_interrupt.connect((self.address, PSM_INTERRUPT))
        self.s_control.settimeout(self.timeout)
        self.s_interrupt.settimeout(self.timeout)
        
    def close(self):
        if self.listening:
            try:
                self.send(bytes((0x13, 0x00)))
                time.sleep(0.05)
                self.send(bytes((0x1A, 0x00)))
                time.sleep(0.05)
            except:
                pass
            self.listening = False
            
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
                
    def openWiimote(self):
        for dev in hid.enumerate():
            if dev['vendor_id'] == WIIMOTE_VID and dev['product_id'] in WIIMOTE_PIDS:
                handle = hid.device()
                try:
                    handle.open_path(dev['path'])
                except:
                    continue
                try:
                    handle.set_nonblocking(False)
                    # status request 
                    if handle.write(bytes([0x15,0x00])) < 2:
                        raise IOError()
                    data = handle.read(32, timeout_ms=500)
                    if not data:
                        raise IOError()
                    print(f"Found Wiimote at: {dev['path']}")
                    return handle
                except:
                    handle.close()
                    continue
        return None

    def initHID(self,connectTimeout=15):
        self.connectCallback("Trying quick connect")
        self.handle = self.openWiimote()
        if not self.handle:
            if os.name == "nt":
                pair_wiimote(timeout=connectTimeout,connectCallback=self.connectCallback)
                #WiiPair(connectTimeout=connectTimeout)
            t = time.monotonic()
            while not self.handle and time.monotonic() < t + self.timeout:
                self.handle = self.openWiimote()
                if not self.handle:
                    time.sleep(0.1)
            if not self.handle:
                print("Failed to connect")
                raise RuntimeError()

        self.handle.set_nonblocking(False)
        
    def recv(self,size):
        if USE_HID:
            return self.handle.read(size)
        else:
            data = self.s_interrupt.recv(size+1)
            if data and data[0] & 0xFF == 0xA1:
                return data[1:]
            else:
                return None
            
    def send(self,out):
        if USE_HID:
            self.handle.write(bytes(out))
        else:
            self.s_interrupt.send(bytes((0xA2,)) + bytes(out))
            
    @property
    def rumble(self):
        return self._rumble != 0
        
    @rumble.setter
    def rumble(self, x):
        self._rumble = 1 if x else 0
        self.send((0x10,self._rumble))
         
    @property
    def led(self):
        return self._leds
    
    @led.setter
    def led(self, l):
        self.send((0x11,l | self._rumble))
        self._leds = l
        
    def read_sync(self,location,address,size):
        output = b''
        if size == 0:
            return output
        read_cmd = bytes((0x17, location, (address&0xFF0000)>>16, (address&0xFF00)>>8, address&0xFF, (size&0xFF00)>>8, size&0xFF))
        self.send(read_cmd)
        time.sleep(0.2)
        t = time.monotonic()
        while time.monotonic() <= t + self.timeout and size > 0:
            data = self.recv(64)
            if data and data[0] == 0x21 and len(data)>6:
                if data[3] & 0xF == 0 and getWord(data, 4) == address & 0xFFFF:
                    n = min(size, len(data)-6)
                    output += bytes(data[6:6+n])
                    address += n
                    size -= n
                else:
                    return None
            elif data and data[0] == 0x22 and data[3] == 0x17 and data[4] != 0:
                return None
            else:
                time.sleep(0.01)
        if size == 0:
            return output
        else:
            return None
    
    def write_reg(self,address,data):
        if len(data) > 16:
            return
        paddedData = list(data) + (16-len(data)) * [0,]
        write_cmd = bytes([0x16, RW_REG, (address&0xFF0000)>>16, (address&0xFF00)>>8, address&0xFF, len(data)] + paddedData)
        self.send(write_cmd)
            
    def enable(self,mode=0,irLevel=DEFAULT_IR_LEVEL): # mode is ignored
        self.listening = True
        self.listenThread = Thread(target = self.listen, args=(irLevel,))
        self.listenThread.start()
        
    def enableExt(self):
        self.write_reg(0xA400F0,(0x55,))
        time.sleep(0.05)
        self.write_reg(0xA400FB,(0x00,))
        time.sleep(0.2)
        for i in range(3):
            d = self.read_sync(RW_REG, 0xa400fe, 2)
            if d is not None:
                if len(d) >= 2 and getWord(d,0) == 0x0000:
                    return EXT_NUNCHUK
                else:
                    return EXT_NONE
            time.sleep(0.1)
        return EXT_NONE
    
    def listen(self,irLevel):

        # enable camera in extended data mode
        if not (self.rpt_mode & RPT_EXT):
            reportMode = 0x33
            reportSize = 18
            irMode = 3 # extended
        else:
            reportMode = 0x37
            reportSize = 22
            irMode = 1 # basic
        if self.rpt_mode & RPT_EXT:
            extType = self.enableExt()
        else:
            extType = EXT_NONE
            
        if self.rpt_mode & RPT_IR:
            self.send(bytes((0x13, 0x04)))
            time.sleep(0.05)
            self.send(bytes((0x1A, 0x04)))
            time.sleep(0.05)
            self.write_reg(0xb00030,(0x01,)) 
            time.sleep(0.05)
            lev = IR_LEVELS[max(min(irLevel,5),1)-1]
            self.write_reg(0xb00000,lev[0])
            time.sleep(0.05)
            self.write_reg(0xb0001a,lev[1])
            time.sleep(0.05)
            self.write_reg(0xb00033,(irMode,)) 
            time.sleep(0.05)
            self.write_reg(0xb00030,(0x08,))
            time.sleep(0.05)
        else:
            self.send(bytes((0x13, 0x00)))
            time.sleep(0.05)
            self.send(bytes((0x1A, 0x00)))
            time.sleep(0.05)
        self.send(bytes((0x12, 0x04, reportMode))) # continuous reporting; TODO: noncontinuous when only buttons of interest
        time.sleep(0.05)

        while self.listening:
            data = self.recv(reportSize)
            if not data:
                continue
            if data[0] == 0x20 and len(data) >= 7:
                if (self.rpt_mode & RPT_EXT) and data[3] & 0x02:
                    extType = self.enableExt()
                else:
                    extType = EXT_NONE
                self.send(bytes((0x12, 0x04, reportMode)))
            if (data[0] == 0x33 and len(data) >= 18) or (data[0] == 0x37 and len(data) >= 22):
                t = time.monotonic()
                buttons = getWord(data,1)
                out = {"buttons": buttons & 0x1F9F}
                x = (0xFF & data[3]) << 2 | (3&(buttons >> 13))
                y = (0xFF & data[4]) << 2 | (2&(buttons >> 4))
                z = (0xFF & data[5]) << 2 | (2&(buttons >> 5))
                out["acc_raw"] = (x,y,z)
                out["acc_calib"] = ( (x-self.accel0gCalibration[0])/(self.accel1gCalibration[0]-self.accel0gCalibration[0]),
                               (y-self.accel0gCalibration[1])/(self.accel1gCalibration[1]-self.accel0gCalibration[1]),
                               (z-self.accel0gCalibration[2])/(self.accel1gCalibration[2]-self.accel0gCalibration[2]) )
                offset = 6
                irData = []
                if data[0] == 0x33:
                    for i in range(4):
                        y = (data[offset+1]&0xFF) | ((data[offset+2]&0xC0)>>6) << 8
                        if y < 1023:
                            x = (data[offset]&0xFF) | ((data[offset+2]&0x30)>>4) << 8
                            s = data[offset+2] & 0xF
                            irData.append(((x,y),s))
                        else:
                            irData.append(None)
                        offset += 3
                    out["ir"] = irData
                elif data[0] == 0x37:
                    for i in range(2):
                        y = (data[offset+1]&0xFF) | ((data[offset+2]&0xC0)>>6) << 8
                        if y < 1023:
                            x = (data[offset]&0xFF) | ((data[offset+2]&0x30)>>4) << 8
                            irData.append(((x,y),1))
                        else:
                            irData.append(None)
                        y = (data[offset+4]&0xFF) | ((data[offset+2]&0xC)>>2) << 8
                        if y < 1023:
                            x = (data[offset+3]&0xFF) | (data[offset+2]&0x3) << 8
                            irData.append(((x,y),1))
                        else:
                            irData.append(None)
                        offset += 5
                    out["ir"] = irData
                    if extType == EXT_NUNCHUK:
                        nunchuk = {}
                        nunchuk["buttons"] = ~data[offset+5] & 0x3                       
                        if any(x & 0xFF != 0xFF for x in data[offset:]):
                            x = (0xFF & data[offset+2]) << 2 | (3&(data[offset+5] >> 2))
                            y = (0xFF & data[offset+3]) << 2 | (3&(data[offset+5] >> 4))
                            z = (0xFF & data[offset+4]) << 2 | (3&(data[offset+5] >> 6))
                            nunchuk["acc_raw"] = (x,y,z)
                            nunchuk["stick"] = (data[offset]&0xFF,data[offset]&0xFF)
                            out["nunchuk"] = nunchuk

                self.state = out
                self.mesg_callback(out,t)        
             
    def calibrate(self):
        data = self.read_sync(RW_EEPROM, CALIBRATION_OFFSET, CALIBRATION_SIZE)
        
        if data and len(data) == CALIBRATION_SIZE:
            self.calibrationRaw = data
            irc = parseIRCalibration(data[IR_CALIBRATION_OFFSET_1:])
            if not irc:
                irc = parseIRCalibration(data[IR_CALIBRATION_OFFSET_2:])
            if irc:
                self.irCalibration = irc
            acc = parseAccelCalibration(data[ACCEL_CALIBRATION_OFFSET:])
            if acc:
                self.accel0gCalibration = acc[0]
                self.accel1gCalibration = acc[1]
                if irc and self.address is None:
                    self.address = hashlib.md5(bytes(data)).hexdigest()
            return acc
        
        return False

if __name__=='__main__':
    w = Wiimote()
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
        
    w.mesg_callback = callback#lambda data,t: print(data)
    w.rpt_mode=RPT_IR|RPT_EXT
    w.enable(mode=RPT_IR|RPT_EXT)
    print("running")
    while True:
        time.sleep(1)
        pass
