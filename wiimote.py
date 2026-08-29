WIIUSE = False

try:
    from cwiid import *
except:
    import wiiuse
    WIIUSE = True
    
if WIIUSE:
    import time
    from threading import Thread
        
    WIIUSE_TIMEOUT = 5

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
    RPT_IR = 0
    RPT_BTN = 1
    RPT_ACC = 2
    RPT_EXT = 3

    # TODO: support more than one wiimote
    class Wiimote:
        def __init__(self):
            self.wiimotes = wiiuse.init(1)
            if not wiiuse.find(wiimotes, 1, WIIUSE_TIMEOUT):
                raise RuntimeError
            if not wiiuse.connect(wiimotes, 1):
                raise RuntimeError
            self.wm = self.wiimotes[0]
            self.mesg_callback = lambda l,t: None
            self.listenThread = None
            self.reportMode = RPT_BTN
            self.state = { 'buttons': 0, 'acc': (0,0,0), 'ir_src': None }
            
        @property
        def rpt_mode(self):
            return self._reportMode
        
        @rpt_mode.setter
        def rpt_mode(self, r):
            wiimote.set_ir(self.wm, 1 if (r & RPT_IR) else 0)
            wiimote.motion_sensing(self.wm, 1 if (r & RPT_ACCEL) else 0)
            self._reportMode = r
        
        @property
        def led(self):
            return self._leds
        
        @led.setter
        def led(self, l):
            wiimote.set_leds(self.wm, l)    
            self._leds = l
            
        def updateState(self):
            newState = { 'buttons': self.wm.buttons }
            if (self._reportMode & RPT_IR) and wiiuse.using_ir(self.wm):
                ir = []
                for i in range(4):
                    if wm.ir.dot[i].visible:
                        ir.append((wm.ir.dot[i].x, wm.ir.dot[i].y))
                    else:
                        ir.append(None)
                newState['ir_src'] = ir
            if (self._reportMode & RPT_ACCEL) and wiiuse.using_acc(self.wm):
                newState['acc'] = (wm.accel.x,wm.accel.y,wm.accel.z)
            self.state = newState
            # TODO: nunchuk
            
        def listenLoop(self):
            while True:
                if wiiuse.poll(wiimotes, 1):
                    self.mesg_callback([], time.monotonic())
                    self.updateState()
                else:
                    sleep(0.01)
                    
        def enable(self, mode):
            # TODO: handle mode
            self.listenThread = Thread(target = self.listenLoop)
            self.listenThread.start()
        
        