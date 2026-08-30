try:
    import uinput
    
    class AbsMouseInput:
        def __init__(self, size, name="AbsMouse"):
            events = [
                uinput.ABS_X + (0,size[0],0,0),
                uinput.ABS_Y + (0,size[1],0,0),
                uinput.BTN_LEFT,
                uinput.BTN_RIGHT
                ]
            self.device = uinput.Device(events, name=name)
            
        def __enter__(self):
            self.device.__enter__()
            return self
   
        def __exit__(self, exc_type, exc_value, exc_traceback):
            self.device.__exit__(exc_type, exc_value, exc_traceback)
            
        def moveTo(self, x, y):
            self.device.emit(uinput.ABS_X,x,syn=False)
            self.device.emit(uinput.ABS_Y,y)
            
        def press(self, button):
            self.device.emit(button, 1)
            
        def release(self, button):
            self.device.emit(button, 0)
            
    class KeyInput:
        def __init__(self, size, name="Keys"):
            events = [(uinput.KEY_ESC[0],i) for i in range(uinput.KEY_ESC[1], uinput.KEY_MICMUTE[1]+1)]
            self.device = uinput.Device(events, name=name)
            
        def __enter__(self):
            self.device.__enter__()
            return self
   
        def __exit__(self, exc_type, exc_value, exc_traceback):
            self.device.__exit__(exc_type, exc_value, exc_traceback)
            
        def emit(self, type, value, syn=False):
            self.device.emit(self,type,value,syn=syn)
            
except ModuleNotFoundError:
    import ctypes 
    from ctypes import wintypes
    
    # Constants for SendInput
    INPUT_MOUSE = 0
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    BTN_LEFT = -1
    BTN_RIGHT = -2

    class MOUSEINPUT(ctypes.Structure):
      _fields_ = [
          ("dx", wintypes.LONG),
          ("dy", wintypes.LONG),
          ("mouseData", wintypes.DWORD),
          ("dwFlags", wintypes.DWORD),
          ("time", wintypes.DWORD),
          ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
      ]


    class INPUT(ctypes.Structure):

      class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

      _anonymous_ = ("_input",)
      _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]


    def send_mouse_event(flags):
        extra = ctypes.c_ulong(0)
        mi = MouseInput(0, 0, 0, flags, 0, ctypes.pointer(extra))
        ii_ = Input_I(mi=mi)
        x = Input(ctypes.c_ulong(INPUT_MOUSE), ii_)
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
            mi = MOUSEINPUT(
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
                        