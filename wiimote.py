WIIUSE = False

set_ir_sensitivity = None
NEVER_CONTINUOUS = True
IR_CALIBRATION_LOCATIONS = ( ((0,2,4),(1,2,6)),  # X1,Y1
                             ((3,2,0),(4,2,2)),  # X2,Y2
                             ((5,7,4),(6,7,6)),  # X3,Y3
                             ((8,7,0),(9,7,2)) ) # X4,Y4 
                             
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
    wm.accel0gCalibration = [(512,512,512)]
    wm.accel1gCalibration = [(616,616,616)]
    wm.irCalibration = [(127,93),(896,93),(896,674),(127,674)]
    irc = parseIRCalibration(buffer[IR_CALIBRATION_OFFSET_1:])
    if not irc:
        irc = parseIRCalibration(buffer[IR_CALIBRATION_OFFSET_2:])
    if irc:
        wm.irCalibration = irc
    acc = parseAccelCalibration(buffer[ACCEL_CALIBRATION_OFFSET:])
    if acc:
        wm.accel0gCalibration = acc[0]
        wm.accel1gCalibration = acc[1]

if not WIIUSE:
    try:
        from cwiid import *
        import ctypes
        import sys
        import time

        libcwiid = ctypes.CDLL(sys.modules['cwiid'].__file__)
        libcwiid.cwiid_read.argtypes = [ ctypes.c_void_p, ctypes.c_uint8, ctypes.c_uint32, ctypes.c_uint16, ctypes.c_void_p ]
        libcwiid.cwiid_read.restype = ctypes.c_int

        IR_LEVELS = ( (b"\x02\x00\x00\x71\x01\x00\x64\x00\xFE", b"\xFD\x05"),
                      (b"\x02\x00\x00\x71\x01\x00\x96\x00\xB4", b"\xB3\x04"),
                      (b"\x02\x00\x00\x71\x01\x00\xAA\x00\x64", b"\x63\x03"),
                      (b"\x02\x00\x00\x71\x01\x00\xC8\x00\x36", b"\x35\x03"),
                      (b"\x02\x00\x00\x71\x01\x00\x72\x00\x20", b"\x1F\x03") )

        def cwiid_set_ir_sensitivity(value):
            if value < 0:
                return
            uint_9 = ctypes.c_uint8*9
            uint_2 = ctypes.c_uint8*2
            ir_block1 = uint_9.in_dll(libcwiid, "ir_block1")
            ir_block2 = uint_2.in_dll(libcwiid, "ir_block2")
            if value < 1:
                value = 1
            elif value > 5:
                value = 5
            ir_block1[:] = IR_LEVELS[value-1][0]
            ir_block2[:] = IR_LEVELS[value-1][1]

        class MyWiimote(Wiimote):
            def __init__(self,connectCallback=None):
                if connectCallback is not None:
                    connectCallback("Press 1+2 on Wii Remote")
                self.irCalibration = None
                self.accel0gCalibration = None
                self.accel1gCalibration = None
                Wiimote.__init__(self)
                self.calibrate()

            def calibrate(self):
                data = self.read(RW_EEPROM, CALIBRATION_OFFSET, CALIBRATION_SIZE)
                if len(data) == CALIBRATION_SIZE:
                    setCalibration(self,data)
                        
        set_ir_sensitivity = cwiid_set_ir_sensitivity
    except ModuleNotFoundError as e:
        WIIUSE = True
        
if WIIUSE:
    # partial cwiid emulation
    import wiiuse
    import time
    import hashlib
    import ctypes
    
    from threading import Thread
        
    WIIUSE_TIMEOUT = 5
    EVENT_DT = .01

    NUNCHUK_BTN_Z = wiiuse.nunchuk_button['Z']
    NUNCHUK_BTN_C = wiiuse.nunchuk_button['C']
    BTN_B = wiiuse.button['B']
    BTN_A = wiiuse.button['A']
    BTN_1 = wiiuse.button['1']
    BTN_2 = wiiuse.button['2']
    BTN_PLUS = wiiuse.button['+']
    BTN_MINUS = wiiuse.button['-']
    BTN_HOME = wiiuse.button['Home']
    BTN_LEFT = wiiuse.button['Left']
    BTN_RIGHT = wiiuse.button['Right']
    BTN_DOWN = wiiuse.button['Down']
    BTN_UP = wiiuse.button['Up']
    LED1_ON = wiiuse.LED_1
    LED2_ON = wiiuse.LED_2
    LED3_ON = wiiuse.LED_3 
    LED4_ON = wiiuse.LED_4 
    RPT_IR = 1
    RPT_BTN = 2
    RPT_ACC = 4
    RPT_EXT = 8
    FLAG_MESG_IFC = 0
    irLevel = 3

    def wiiuse_set_ir_sensitivity(level):
        global irLevel

        if level < 0:
            return

        irLevel = level

    set_ir_sensitivity = wiiuse_set_ir_sensitivity

    # TODO: support more than one wiimote
    class MyWiimote:
        def __init__(self,connectCallback=None):
            if connectCallback is not None:
                connectCallback("Press 1+2 on Wii Remote")
            self.wiimotes = wiiuse.init(1)
            if not wiiuse.find(self.wiimotes, 1, WIIUSE_TIMEOUT):
                raise RuntimeError
            if not wiiuse.connect(self.wiimotes, 1):
                raise RuntimeError
            self.wm = self.wiimotes[0]
            self.mesg_callback = lambda l,t: None
            self.listenThread = None
            self._reportMode = RPT_BTN
            self.state = { 'buttons': 0, 'acc': (128,128,156), 'ir_src': [None,None,None,None] }
            self.irCalibration = None
            self.accel0gCalibration = None
            self.accel1gCalibration = None
            try:
                self.address = self.wm.contents.bdaddr_str.decode()
            except:
                self.address = "wiiuse_wiimote";
                
        @property
        def rpt_mode(self):
            return self._reportMode
        
        @rpt_mode.setter
        def rpt_mode(self, r):
            wiiuse.set_ir(self.wm, 1 if (r & RPT_IR) else 0)
            wiiuse.motion_sensing(self.wm, 1 if (r & RPT_ACC) else 0)
            self._reportMode = r
            wiiuse.set_flags(self.wm, 0, wiiuse.SMOOTHING)
            if r & RPT_IR:
                wiiuse.set_ir_sensitivity(self.wm, irLevel)
            if (r & (RPT_IR | RPT_ACC)) and not NEVER_CONTINUOUS:
                wiiuse.set_flags(self.wm, wiiuse.CONTINUOUS, 0)
            else:
                wiiuse.set_flags(self.wm, 0, wiiuse.CONTINUOUS)
            self.calibrate()
        
        @property
        def led(self):
            return self._leds
        
        @led.setter
        def led(self, l):
            wiiuse.set_leds(self.wm, l)    
            self._leds = l
            
        def updateState(self):
            newState = { 'buttons': self.wm.contents.btns }
            if (self._reportMode & RPT_IR) and wiiuse.using_ir(self.wm.contents):
                ir = []
                for i in range(4):
                    if self.wm.contents.ir.dot[i].visible:
                        ir.append({'pos':(1023-self.wm.contents.ir.dot[i].rx, self.wm.contents.ir.dot[i].ry)})
                    else:
                        ir.append(None)
                newState['ir_src'] = ir
            if (self._reportMode & RPT_ACC) and wiiuse.using_acc(self.wm.contents):
                newState['acc'] = (0xFF&self.wm.contents.accel.x,0xFF&self.wm.contents.accel.y,0xFF&self.wm.contents.accel.z)
            self.state = newState
            # TODO: nunchuk
            
        def listenLoop(self):
            while True:
                haveEvent = False
                t = time.monotonic()
                if wiiuse.poll(self.wiimotes, 1):
                    if self.wm.contents.event == wiiuse.EVENT:
                        haveEvent = True
                        self.updateState()
                        self.mesg_callback([], t)
                if not haveEvent:
                    time.sleep(EVENT_DT)
                    
        def enable(self, mode):
            # TODO: handle mode
            self.listenThread = Thread(target = self.listenLoop)
            self.listenThread.start()

        def calibrate(self): # call before enable()
            self.irCalibration = None
            self.accel0gCalibration = None
            self.accel1gCalibration = None
            buffer = ctypes.create_string_buffer(CALIBRATION_SIZE)
            wiiuse.read_data(self.wm, buffer, CALIBRATION_OFFSET, CALIBRATION_SIZE)
            t = time.monotonic()
            while time.monotonic() < t + 6:
                if wiiuse.poll(self.wiimotes, 1):
                    if self.wm.contents.event == wiiuse.READ_DATA and not self.irCalibration and not self.accel0gCalibration:
                        setCalibration(self,buffer)
                        if self.irCalibration and self.accel0gCalibration:
                            if self.address == "wiiuse_wiimote":
                                self.address = hashlib.md5(buffer.raw).hexdigest()
                    time.sleep(.01)
        
    
