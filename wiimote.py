WIIUSE = True

if not WIIUSE:
    try:
        from cwiid import *
    except:
        WIIUSE = True
    
if WIIUSE:
    # partial cwiid emulation
    import wiiuse
    import time
    from threading import Thread
        
    WIIUSE_TIMEOUT = 5
    EVENT_DT = 0.01

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
            self.reportMode = RPT_BTN
            self.state = { 'buttons': 0, 'acc': (128,128,156), 'ir_src': [None,None,None,None] }
            
        @property
        def rpt_mode(self):
            return self._reportMode
        
        @rpt_mode.setter
        def rpt_mode(self, r):
            wiiuse.set_ir(self.wm, 1 if (r & RPT_IR) else 0)
            wiiuse.motion_sensing(self.wm, 1 if (r & RPT_ACC) else 0)
            self._reportMode = r
            wiiuse.set_flags(self.wm, 0, wiiuse.SMOOTHING)
            if r & (RPT_IR | RPT_ACC):
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
                dt = time.monotonic() - t 
                if dt < EVENT_DT:
                    time.sleep(EVENT_DT - dt)
                    
        def enable(self, mode):
            # TODO: handle mode
            self.listenThread = Thread(target = self.listenLoop)
            self.listenThread.start()
