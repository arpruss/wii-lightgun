import sys
import math
import time
import os
import threading
from tkinter import *

FONT_TEMPLATE = "Helvetica %d"
FONT_SIZE = 0.05
BLACK = (0,0,0)
WHITE = (255,255,255)
RED = (255,0,0)
GRAY = (64,64,64)
DARK_GREEN = (0,64,0)
VERY_DARK_GREEN = (0,32,0)
SIZE = None
running = False

def rgb(c):
    return "#%02x%02x%02x" % c
    
def close(event=None):
    global running
    tk.destroy()
    running = False

def displayInit():
    global tk,textData,canvas,MYFONT,thread,running,SIZE,PXSCALE
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
    PXSCALE = math.floor(SIZE[1]/1050)
    if PXSCALE < 1:
        PXSCALE = 1
    
    tk.bind("<Escape>", close)
    tk.protocol("WM_DELETE_WINDOW", close)
    running = True
    
    return SIZE
    
def drawCameraView():  
    global cameraViewID,cameraViewHeight,cameraViewCenter
    cameraViewHeight = int(SIZE[1] * 0.4)
    width = cameraViewHeight * 4 // 3
    x = SIZE[0] // 2 - width//2
    y = SIZE[1] // 4 - cameraViewHeight//2
    cameraViewCenter = (SIZE[0]//2,SIZE[1]//4)
    canvas.delete("cameraView")
    cameraViewID = canvas.create_rectangle(x,y,x+width,y+cameraViewHeight,fill=rgb(DARK_GREEN),width=0,tags="cameraView")
    
def drawVerticalArrow(xy,length,tag,color=WHITE):
    canvas.delete("arrow_"+tag)
    x,y = xy
    c = rgb(color)
    canvas.create_line(x,y,x,y+length,width=2,tags=tag,fill=c)
    canvas.create_line(x,y,x-length//3,y+length//3,width=2,tags=tag,fill=c)
    canvas.create_line(x,y,x+length//3,y+length//3,width=2,tags=tag,fill=c)

def drawCross(xy,color=RED):
    thickness=3
    size=0.25
    l = size*SIZE[1]/2.
    x = xy[0]*SIZE[0]
    y = (1-xy[1])*SIZE[1]
    t = thickness*PXSCALE
    c = rgb(color)
    canvas.delete("cross")
    canvas.create_rectangle(x-l//2,y-t//2,x-l//2+l,y-t//2+t,width=0,fill=c,tags="cross")
    canvas.create_rectangle(x-t//2,y-l//2,x-t//2+t,y-l//2+l,width=0,fill=c,tags="cross")
    
def drawPoint(x,y,size,n,real):
    x = int(cameraViewCenter[0] + x * cameraViewHeight)
    y = int(cameraViewCenter[1] + (-y) * cameraViewHeight)
    s = int(size/768*cameraViewHeight)
    if s < 0:
        s = 1
    rx = x-s//2
    ry = y-s//2
    c = rgb(RED) if real else rgb(GRAY)
    tag = "point_"+str(n)
    canvas.delete(tag)
    canvas.create_text(x,y,text=str(n+1),fill=c,font=MYFONT,anchor="center",tags=tag)
    canvas.create_rectangle(rx,ry,rx+s,ry+s,fill=rgb(WHITE),width=0,tags=tag)
    
def drawText(s,x=.5,y=.5,color=WHITE):
    tag = "text_"+str(x)+","+str(y)
    canvas.delete(tag)
    canvas.create_text(x*SIZE[0],y*SIZE[1],text=s,fill=rgb(color),font=MYFONT,anchor="n",tags=tag)
        
def clear():
    canvas.delete("all")
    textData.clear()
    
def update():
    if running:
        tk.update_idletasks()
        tk.update()
    
if __name__ == '__main__':
    displayInit()
    drawCameraView()
    drawCross((0.25,0.25))
    drawPoint(.25,.25,1,1,True)
    update()
    time.sleep(1)
    drawCross((0.26,0.26))
    drawVerticalArrow((12,12),100,"1")
    drawPoint(.3,.3,1,1,False)
    drawText("Hello",y=.5)
    while running:
        update()
        time.sleep(0.01)
        