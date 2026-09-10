import sys
import time
import os
import threading
from tkinter import *

FONT_TEMPLATE = "Helvetica %d"
FONT_SIZE = 0.05
WHITE = (255,255,255)
SIZE = None
running = False

def rgb(c):
    return "#%02x%02x%02x" % c
    
def close(event=None):
    global running
    tk.destroy()
    running = False

def displayInit():
    global tk,textData,canvas,MYFONT,thread,running,SIZE
    if os.name == 'nt':
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Process_Per_Monitor_DPI_Aware
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()  # Fallback for older Windows versions
            except Exception:
                pass
    tk = Tk()
    if os.name != 'nt':
        tk.tk.call("tk", "scaling", 1.0)
    tk.attributes("-fullscreen", True)
    tk.config(cursor="none")

    SIZE = tk.winfo_screenwidth(), tk.winfo_screenheight()

    canvas = Canvas(tk, width=SIZE[0], height=SIZE[1], highlightthickness=0)
    canvas.configure(bg="black")
    canvas.pack()
    textData = {}
    MYFONT = FONT_TEMPLATE % int(SIZE[1] * FONT_SIZE)
    
    tk.bind("<Escape>", close)
    tk.protocol("WM_DELETE_WINDOW", close)
    running = True
    
    return SIZE
    
def drawText(s,x=.5,y=.5,color=WHITE):
    if (x,y) not in textData:
        id = canvas.create_text(x*SIZE[0],y*SIZE[1],text=s,fill=rgb(color),font=MYFONT,anchor="n")
    else:
        canvas.itemconfig(textData[(x,y)],text=s)       
        
def clear():
    canvas.delete("all")
    textData.clear()
    
def update():
    if running:
        tk.update_idletasks()
        tk.update()
    
if __name__ == '__main__':
    displayInit()
    drawText("Hello",y=.5)
    while running:
        update()
        time.sleep(0.01)
        