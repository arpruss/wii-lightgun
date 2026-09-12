import sys
import math
import time
import os
import threading
from tkinter import *

FONT_TEMPLATE = "Helvetica %d"
FONT_SIZE = 0.02
BLACK = (0,0,0)
WHITE = (255,255,255)
RED = (255,0,0)
GRAY = (64,64,64)
DARK_GREEN = (0,64,0)
VERY_DARK_GREEN = (0,32,0)
WINDOW_SIZE = None
SCREEN_SIZE = None
running = False
keys = ""
canvas = None

def keyPressed(event):
    global keys
    keys += event.char

def getKeys():
    global keys
    k = keys
    keys = ""
    return k
    
def isRunning():
    return running

def rgb(c):
    return "#%02x%02x%02x" % c
    
def close(event=None):
    global running,canvas
    try:
        tk.destroy()
    except:
        pass
    running = False
    canvas = None

def getScreenSize():
    return SCREEN_SIZE

def init(ratio=1,cursor=True,name=None):
    global tk,SCREEN_SIZE
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
    if name is not None:
        tk.title(name)
    if os.name != 'nt':
        tk.tk.call("tk", "scaling", 1.0)

    SCREEN_SIZE = tk.winfo_screenwidth(), tk.winfo_screenheight()
        
def setWindow(ratio=1):
    global canvas,MYFONT,thread,running,WINDOW_SIZE,PXSCALE
    
    if canvas is not None:
        canvas.destroy()

    if ratio == 1:
        tk.attributes("-fullscreen", True)
        tk.config(cursor="none")
        WINDOW_SIZE = SCREEN_SIZE
    else:
        WINDOW_SIZE = int(SCREEN_SIZE[0] * ratio),int(SCREEN_SIZE[1] * ratio)
        tk.config(cursor="arrow")
        x = (SCREEN_SIZE[0] - WINDOW_SIZE[0]) // 2
        y = (SCREEN_SIZE[1] - WINDOW_SIZE[1]) // 2

        tk.geometry(f"{WINDOW_SIZE[0]}x{WINDOW_SIZE[1]}+{x}+{y}")
    
    tk.bind("<Escape>", close)
    tk.bind("<Key>", keyPressed)
    tk.protocol("WM_DELETE_WINDOW", close)
    running = True

    canvas = Canvas(tk, width=WINDOW_SIZE[0], height=WINDOW_SIZE[1], highlightthickness=0)
    canvas.configure(bg="black")
    canvas.pack()
    keys = None
    MYFONT = FONT_TEMPLATE % int(WINDOW_SIZE[1] * FONT_SIZE)
    PXSCALE = math.floor(WINDOW_SIZE[1]/1050)
    if PXSCALE < 1:
        PXSCALE = 1
        
    return WINDOW_SIZE
    
def drawCameraView():  
    global cameraViewHeight,cameraViewCenter
    cameraViewHeight = int(WINDOW_SIZE[1] * 0.4)
    width = cameraViewHeight * 4 // 3
    x = WINDOW_SIZE[0] // 2 - width//2
    y = WINDOW_SIZE[1] // 4 - cameraViewHeight//2
    cameraViewCenter = (WINDOW_SIZE[0]//2,WINDOW_SIZE[1]//4)
    canvas.delete("cameraView")
    canvas.create_rectangle(x,y,x+width,y+cameraViewHeight,fill=rgb(VERY_DARK_GREEN),width=0,tags="cameraView")
    
def drawRect(x,y,w,h,tag=None,color=WHITE):
    if tag is not None:
        canvas.delete(tag)
    canvas.create_rectangle(x,y,x+w,y+h,fill=rgb(color),width=0,tags=tag)
    
def drawVerticalArrow(xy,length,tag=None,color=WHITE):
    if tag is not None:
        canvas.delete(tag)
    x,y = xy
    c = rgb(color)
    canvas.create_line(x,y,x,y+length,width=2,tags=tag,fill=c)
    canvas.create_line(x,y,x-length//3,y+length//3,width=2,tags=tag,fill=c)
    canvas.create_line(x,y,x+length//3,y+length//3,width=2,tags=tag,fill=c)

def drawCross(xy,color=RED):
    thickness=3
    size=0.25
    l = size*WINDOW_SIZE[1]/2.
    x = xy[0]*WINDOW_SIZE[0]
    y = (1-xy[1])*WINDOW_SIZE[1]
    t = thickness*PXSCALE
    c = rgb(color)
    canvas.delete("cross")
    canvas.create_rectangle(x-l//2,y-t//2,x-l//2+l,y-t//2+t,width=0,fill=c,tags="cross")
    canvas.create_rectangle(x-t//2,y-l//2,x-t//2+t,y-l//2+l,width=0,fill=c,tags="cross")
    
def clearPoints():
    canvas.delete("points")
    
def drawPoint(x,y,size,n,real,label):
    x = int(cameraViewCenter[0] + x * cameraViewHeight)
    y = int(cameraViewCenter[1] + (-y) * cameraViewHeight)
    s = int(size/768*cameraViewHeight)
    if s < 1:
        s = 1
    s += 1
    rx = x-s//2
    ry = y-s//2
    c = rgb(RED) if real else rgb(GRAY)
    if label:
        canvas.create_text(x,y,text=str(n+1),fill=c,font=MYFONT,anchor="center",tags="points")
    else:
        canvas.create_rectangle(rx,ry,rx+s,ry+s,fill=rgb(WHITE),width=0,tags="points")
    
def drawText(s,x=.5,y=.5,color=WHITE):
    tag = "text_"+str(x)+","+str(y)
    canvas.delete(tag)
    if s is not None:
        canvas.create_text(x*WINDOW_SIZE[0],y*WINDOW_SIZE[1],text=s,fill=rgb(color),font=MYFONT,anchor="n",tags=tag)
        
def clear(color=BLACK):
    canvas.delete("all")
    canvas.configure(bg=rgb(color))
    
def update():
    if running:
        tk.update_idletasks()
        tk.update()
        
def delete(tag):
    canvas.delete(tag)
    
if __name__ == '__main__':
    init()
    print(SCREEN_SIZE)
    setWindow(ratio=0.5)
    drawCameraView()
    drawCross((0.25,0.25))
    drawPoint(.25,.25,1,1,True,True)
    update()
    setWindow(ratio=0.75)
    time.sleep(1)
    drawCross((0.26,0.26))
    drawVerticalArrow((12,12),100,"1")
    drawPoint(.3,.3,1,1,False,True)
    drawText("Hello",y=.5)
    while running:
        update()
        time.sleep(0.01)
        