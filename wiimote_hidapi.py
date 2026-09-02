import os
import time
from threading import Thread
if os.name == 'nt':
    USE_HID = True
else:
    USE_HID = False

if USE_HID:
    import hid
else:
    import wiimote_scan
    import socket

WIIUSE = False
WIIMOTE_VID = 0x057e
WIIMOTE_PIDS = [0x0306, 0x0330]

PSM_CONTROL = 17
PSM_INTERRUPT = 19

RW_EEPROM = 0
RW_REG = 0x04


EVENT_DT = .01

set_ir_sensitivity = None
NEVER_CONTINUOUS = True
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

def parseIRCalibration(data):
    if len(data) < 11:
        return None
    s = (0x55 + sum(data[i] & 0xFF for i in range(10))) & 0xFF
    if s != (data[10] & 0xFF):
        return None
    def getCoordinate(bits07_offset,bits89_offset,bits89_shift):
        return (data[bits07_offset] & 0xFF) | (((data[bits89_offset] >> bits89_shift) & 0x3) << 8)    
    
    return tuple( (getCoordinate(*icl[0]), getCoordinate(*icl[1])) for icl in IR_CALIBRATION_LOCATIONS)
 
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

def setCalibration(wm,buffer):
    irc = parseIRCalibration(buffer[IR_CALIBRATION_OFFSET_1:])
    if not irc:
        irc = parseIRCalibration(buffer[IR_CALIBRATION_OFFSET_2:])
    if irc:
        wm.irCalibration = irc
    acc = parseAccelCalibration(buffer[ACCEL_CALIBRATION_OFFSET:])
    if acc:
        wm.accel0gCalibration = acc[0]
        wm.accel1gCalibration = acc[1]
        
def getWord(data, offset):
    return (data[offset] & 0xFF) << 8 | (data[offset+1] & 0xFF)
    
class MyWiimote:
    def __init__(self, timeout=5):
        self.timeout = timeout
        if USE_HID:
            self.initHID()
        else:
            self.initSocket()
        self.led = 0x60
        self.calibrate()
        self.led = 0xF0-0x60
        
    def initSocket(self):
        mac = wiimote_scan.scan_wiimote_dbus_poll(timeout=10)
        if not mac:
            raise RuntimeError()
        self.address = mac
        self.s_control = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.s_interrupt = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)        
        self.s_control.connect((self.address, PSM_CONTROL))
        self.s_interrupt.connect((self.address, PSM_INTERRUPT))

    def initHID(self):
        target_path = None
        t = time.monotonic()
        while not target_path and time.monotonic() < t + self.timeout:
            for dev in hid.enumerate():
                if dev['vendor_id'] == WIIMOTE_VID and dev['product_id'] in WIIMOTE_PIDS:
                    target_path = dev['path']
                    print(f"Found Wiimote at: {target_path}")
                    break
            time.sleep(0.2)
        if not target_path:
            raise RuntimeError()

        # Open the hidraw device path
        self.handle = hid.device()
        self.handle.open_path(target_path)
        self.handle.set_nonblocking(True)
        self.callback = lambda data,t: None
        
    def recv(self,size):
        if USE_HID:
            return self.handle.read(size)
        else:
            data = self.s_interrupt.recv(size)
            if data:
                return data[1:]
            else:
                return data
            
    def send(self,out):
        if USE_HID:
            self.handle.write(bytes(out))
        else:
            self.s_interrupt.send(bytes((0xA2,)) + bytes(out))
        
    @property
    def led(self):
        return self._leds
    
    @led.setter
    def led(self, l):
        self.send((0x11,l))
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
            if data and data[0] == 0x21 and data[3] & 0xF == 0 and  len(data)>6 and getWord(data, 4) == address:
                output += bytes(data[6:])
                n = min(size, len(data)-6)
                address += n
                size -= n
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
            
    def enable(self,mode,irLevel=5): # mode is ignored
        self.listenThread = Thread(target = self.listening, args=(mode,irLevel,))
        self.listenThread.start()
    
    def listening(self,mode,irLevel):
        # enable camera in extended data mode
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
        self.write_reg(0xb00033,(2,)) # extended
        time.sleep(0.05)
        self.write_reg(0xb00030,(0x08,))
        time.sleep(0.05)
        self.send(bytes((0x12, 0x04, 0x33))) # continuous reporting
        time.sleep(0.05)
        print("waiting")
        while True:
            data = self.recv(19)
            if data and data[0] == 0x33 and len(data) == 18:
                t = time.monotonic()
                buttons = getWord(data,1)
                out = {"buttons": buttons & 0x1F9F}
                x = (0xFF & data[3]) << 2 | (3&(buttons >> 13))
                y = (0xFF & data[4]) << 2 | (2&(buttons >> 4))
                z = (0xFF & data[5]) << 2 | (2&(buttons >> 5))
                out["raw_acc"] = (x,y,z)
                out["acc"] = ( (x-self.accel0gCalibration[0])/self.accel1gCalibration[0],
                               (y-self.accel0gCalibration[1])/self.accel1gCalibration[1],
                               (z-self.accel0gCalibration[2])/self.accel1gCalibration[2] )
                offset = 6
                irData = []
                for i in range(4):
                    x = (data[offset]&0xFF) | ((data[offset+2]&0x30)>>4) << 8
                    y = (data[offset+1]&0xFF) | ((data[offset+2]&0xC0)>>6) << 8
                    if y < 1023:
                        s = data[offset+2] & 0xF
                        irData.append(((x,y),s))
                    else:
                        irData.append(None)
                    offset += 3
                out["ir"] = irData
                self.callback(out,t)
            time.sleep(EVENT_DT)
        
    def calibrate(self):
        data = self.read_sync(RW_EEPROM, CALIBRATION_OFFSET, CALIBRATION_SIZE)
        if data:
            setCalibration(self, data)
    

if __name__=='__main__':
    w = MyWiimote()
    print(w.irCalibration)
    print(w.accel0gCalibration)
    print(w.accel1gCalibration)
    w.callback = lambda data,t: print(data)
    print("enabling")
    w.enable(0)
    while True:
        time.sleep(1)
        pass
