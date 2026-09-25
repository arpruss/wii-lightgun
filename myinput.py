try:
    from uinput import *
    
    class AbsMouseInput:
        def __init__(self, size, name="AbsMouse"):
            events = [
                ABS_X + (0,size[0],0,0),
                ABS_Y + (0,size[1],0,0),
                BTN_LEFT,
                BTN_RIGHT
                ]
            self.device = Device(events, name=name)
            
        def __enter__(self):
            self.device.__enter__()
            return self
   
        def __exit__(self, exc_type, exc_value, exc_traceback):
            self.device.__exit__(exc_type, exc_value, exc_traceback)
            
        def moveTo(self, x, y):
            self.device.emit(ABS_X,x,syn=False)
            self.device.emit(ABS_Y,y)
            
        def press(self, button):
            self.device.emit(button, 1)
            
        def release(self, button):
            self.device.emit(button, 0)
            
    class KeyInput:
        def __init__(self, name="Keys"):
            events = [(KEY_ESC[0],i) for i in range(KEY_ESC[1], KEY_MICMUTE[1]+1)]
            self.device = Device(events, name=name)
            
        def __enter__(self):
            self.device.__enter__()
            return self
   
        def __exit__(self, exc_type, exc_value, exc_traceback):
            self.device.__exit__(exc_type, exc_value, exc_traceback)
            
        def emit(self, type, value, syn=False):
            self.device.emit(self,type,value,syn=syn)

        def press(self, button):
            self.device.emit(button, 1)
            
        def release(self, button):
            self.device.emit(button, 0)
            
except ModuleNotFoundError:
    import ctypes 
    from ctypes import wintypes
    
    # Constants for SendInput
    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    KEYEVENTF_KEYUP = 0x0002
    BTN_LEFT = -1
    BTN_RIGHT = -2
    KEY_A = ord('A')
    KEY_B = ord('B')
    KEY_C = ord('C')
    KEY_D = ord('D')
    KEY_E = ord('E')
    KEY_F = ord('F')
    KEY_G = ord('G')
    KEY_H = ord('H')
    KEY_I = ord('I')
    KEY_J = ord('J')
    KEY_K = ord('K')
    KEY_L = ord('L')
    KEY_M = ord('M')
    KEY_N = ord('N')
    KEY_O = ord('O')
    KEY_P = ord('P')
    KEY_Q = ord('Q')
    KEY_R = ord('R')
    KEY_S = ord('S')
    KEY_T = ord('T')
    KEY_U = ord('U')
    KEY_V = ord('V')
    KEY_W = ord('W')
    KEY_X = ord('X')
    KEY_Y = ord('Y')
    KEY_Z = ord('Z')
    KEY_SPACE = ord(' ')
    KEY_ENTER = 0x0D
    KEY_DOWN = 0x28
    KEY_UP = 0x26
    KEY_LEFT = 0x25
    KEY_RIGHT = 0x27
    KEY_F1 = 0x70
    KEY_F2 = 0x71
    KEY_F3 = 0x72
    KEY_F4 = 0x73
    KEY_F5 = 0x74
    KEY_F6 = 0x75
    KEY_F7 = 0x76
    KEY_F8 = 0x77
    KEY_F9 = 0x78
    KEY_F10 = 0x79
    KEY_TAB = 0x09
    KEY_LEFTBRACE = 0xDB
    KEY_RIGHTBRACE = 0xDD
    KEY_ESC = 0x1B

    class MouseInput(ctypes.Structure):
      _fields_ = [
          ("dx", wintypes.LONG),
          ("dy", wintypes.LONG),
          ("mouseData", wintypes.DWORD),
          ("dwFlags", wintypes.DWORD),
          ("time", wintypes.DWORD),
          ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
      ]

    PUL = ctypes.POINTER(ctypes.c_ulong)

    class KeyBdInput(ctypes.Structure):
      _fields_ = [
          ("wVk", ctypes.c_ushort),
          ("wScan", ctypes.c_ushort),
          ("dwFlags", ctypes.c_ulong),
          ("time", ctypes.c_ulong),
          ("dwExtraInfo", PUL),
      ]


    class HardwareInput(ctypes.Structure):
      _fields_ = [
          ("uMsg", ctypes.c_ulong),
          ("wParamL", ctypes.c_short),
          ("wParamH", ctypes.c_ushort),
      ]

    class INPUT(ctypes.Structure):

      class _INPUT(ctypes.Union):
        _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]

      _anonymous_ = ("_input",)
      _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]


    def send_mouse_event(flags):
        extra = ctypes.c_ulong(0)
        mi = MouseInput(0, 0, 0, flags, 0, ctypes.pointer(extra))
        x = INPUT(type=INPUT_MOUSE, mi=mi)
        ctypes.windll.user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))
        
    def send_key(code,down):
        extra = ctypes.c_ulong(0)
        ki = KeyBdInput(code, 0, 0 if down else KEYEVENTF_KEYUP, 0, ctypes.pointer(extra))
        x = INPUT(type=INPUT_KEYBOARD, ki=ki)
        ctypes.windll.user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))        
  
    class AbsMouseInput:
        def __init__(self, size, name="AbsMouse"):
            self.size = size
            
        def __enter__(self):
            return self
   
        def __exit__(self, exc_type, exc_value, exc_traceback):
            return
            
        def moveTo(self, x, y):
            x = int(65535 * max(min(x, self.size[0]-1),0) / (self.size[0]-1))
            y = int(65535 * max(min(y, self.size[1]-1),0) / (self.size[1]-1))
            
            extra = ctypes.c_ulong(0)
            mi = MouseInput(
              dx=x,
              dy=y,
              mouseData=0,
              dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
              time=0,
              dwExtraInfo=ctypes.pointer(extra),
            )
            data = INPUT(type=INPUT_MOUSE, mi=mi)
            ctypes.windll.user32.SendInput(1, ctypes.byref(data), ctypes.sizeof(data))    
                        
        def press(self, btn):
            if btn == BTN_LEFT:
                send_mouse_event(MOUSEEVENTF_LEFTDOWN)
            elif btn == BTN_RIGHT:
                send_mouse_event(MOUSEEVENTF_RIGHTDOWN)

        def release(self, btn):
            if btn == BTN_LEFT:
                send_mouse_event(MOUSEEVENTF_LEFTUP)
            elif btn == BTN_RIGHT:
                send_mouse_event(MOUSEEVENTF_RIGHTUP)

    class KeyInput:
        def __init__(self, name="KeyInput"):
            return
            
        def __enter__(self):
            return self
   
        def __exit__(self, exc_type, exc_value, exc_traceback):
            return
            
        def press(self, btn):
            send_key(btn, True)

        def release(self, btn):
            send_key(btn, False)
                                    

    KEY_A = ord('A')
    KEY_B = ord('B')
    KEY_C = ord('C')
    KEY_D = ord('D')
    KEY_E = ord('E')
    KEY_F = ord('F')
    KEY_G = ord('G')
    KEY_H = ord('H')
    KEY_I = ord('I')
    KEY_J = ord('J')
    KEY_K = ord('K')
    KEY_L = ord('L')
    KEY_M = ord('M')
    KEY_N = ord('N')
    KEY_O = ord('O')
    KEY_P = ord('P')
    KEY_Q = ord('Q')
    KEY_R = ord('R')
    KEY_S = ord('S')
    KEY_T = ord('T')
    KEY_U = ord('U')
    KEY_V = ord('V')
    KEY_W = ord('W')
    KEY_X = ord('X')
    KEY_Y = ord('Y')
    KEY_Z = ord('Z')
    KEY_0 = ord('0')
    KEY_1 = ord('1')
    KEY_2 = ord('2')
    KEY_3 = ord('3')
    KEY_4 = ord('4')
    KEY_5 = ord('5')
    KEY_6 = ord('6')
    KEY_7 = ord('7')
    KEY_8 = ord('8')
    KEY_9 = ord('9')
    KEY_SPACE = ord(' ')
    KEY_ENTER = 0x0D
    KEY_DOWN = 0x28
    KEY_UP = 0x26
    KEY_LEFT = 0x25
    KEY_RIGHT = 0x27
    KEY_F1 = 0x70
    KEY_F2 = 0x71
    KEY_F3 = 0x72
    KEY_F4 = 0x73
    KEY_F5 = 0x74
    KEY_F6 = 0x75
    KEY_F7 = 0x76
    KEY_F8 = 0x77
    KEY_F9 = 0x78
    KEY_F10 = 0x79
    KEY_F11 = 0x7A
    KEY_F12 = 0x7B
    KEY_TAB = 0x09
    KEY_LEFTBRACE = 0xDB
    KEY_RIGHTBRACE = 0xDD
    KEY_ESC = 0x1B

                                    
KEY_DICT = { "a":KEY_A, "b":KEY_B, "c":KEY_C, "d":KEY_D, "e":KEY_E,
    "f":KEY_F, "g":KEY_G, "h":KEY_H, "i":KEY_I, "j":KEY_J, "k":KEY_K,
    "l":KEY_L, "m":KEY_M, "n":KEY_N, "o":KEY_N, "p":KEY_P, "q":KEY_Q,
    "r":KEY_R, "s":KEY_S, "t":KEY_T, "u":KEY_U, "v":KEY_V, "w":KEY_V,
    "x":KEY_X, "y":KEY_Y, "z":KEY_Z, 
    "0":KEY_0, "1":KEY_1, "2":KEY_2, "3":KEY_3, "4":KEY_4, "5":KEY_5,
    "6":KEY_6, "7":KEY_7, "8":KEY_8, "9":KEY_9, 
    "space":KEY_SPACE, "enter":KEY_ENTER, 
    "down":KEY_DOWN, "left":KEY_LEFT, "right":KEY_RIGHT, "up":KEY_UP,
    "f1":KEY_F1, "f2":KEY_F2, "f3":KEY_F3, "f4":KEY_F4, "f5":KEY_F5, "f6":KEY_F6,
    "f7":KEY_F1, "f8":KEY_F2, "f9":KEY_F3, "f10":KEY_F4, "f11":KEY_F5, "f12":KEY_F6,
    "[":KEY_LEFTBRACE, "]":KEY_RIGHTBRACE, "esc":KEY_ESC, "mouseleft":BTN_LEFT, "mouseright":BTN_RIGHT }
    