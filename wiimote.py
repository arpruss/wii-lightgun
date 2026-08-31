WIIUSE = False

set_ir_sensitivity = None
NEVER_CONTINUOUS = True

if not WIIUSE:
    try:
        from cwiid import *
        import ctypes
        import sys
        
        IR_LEVELS = ( (b"\x02\x00\x00\x71\x01\x00\x64\x00\xFE", b"\xFD\x05"),
                      (b"\x02\x00\x00\x71\x01\x00\x96\x00\xB4", b"\xB3\x04"),
                      (b"\x02\x00\x00\x71\x01\x00\xAA\x00\x64", b"\x63\x03"),
                      (b"\x02\x00\x00\x71\x01\x00\xC8\x00\x36", b"\x35\x03"),
                      (b"\x02\x00\x00\x71\x01\x00\x72\x00\x20", b"\x1F\x03") )

        def cwiid_set_ir_sensitivity(value):
            if value < 0:
                return
            lib = ctypes.CDLL(sys.modules['cwiid'].__file__)
            uint_9 = ctypes.c_uint8*9
            uint_2 = ctypes.c_uint8*2
            ir_block1 = uint_9.in_dll(lib, "ir_block1")
            ir_block2 = uint_2.in_dll(lib, "ir_block2")
            if value < 1:
                value = 1
            elif value > 5:
                value = 5
            ir_block1[:] = IR_LEVELS[value-1][0]
            ir_block2[:] = IR_LEVELS[value-1][1]

        set_ir_sensitivity = cwiid_set_ir_sensitivity
    except ModuleNotFoundError as e:
        print(e)
        WIIUSE = True
    
if WIIUSE:
    # partial cwiid emulation
    import wiiuse
    import time
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
    class Wiimote:
        def __init__(self):
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
