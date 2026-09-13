import sys
import math
import time
import os
import threading
from tkinter import *

FONT_TEMPLATE = "Helvetica %d"
FONT_SIZE = 0.025
BLACK = (0,0,0)
WHITE = (255,255,255)
RED = (255,0,0)
GRAY = (72,72,72)
DARK_GREEN = (0,64,0)
VERY_DARK_GREEN = (0,32,0)
WINDOW_SIZE = None
SCREEN_SIZE = None
running = False
keys = ""
canvas = None
WIIMOTE_LENGTH = 147.
SIGHT_OFFSET_X=30.7
SIGHT_OFFSET_Y1=2
SIGHT_OFFSET_Y2=WIIMOTE_LENGTH-2
WIIMOTE = [ [5.872285531,0.068569411],[3.08991926,1.461870427],[1.248693633,3.596906946],[0.407072306,6.599485689],[0.119271256,12.037491382],[0,28.938473046],[0.205194694,29.328911761],[0.967497906,30.137250293],[2.171985783,30.327863222],[22.055316623,30.520243634],[22.541037053,30.711285651],[22.90677754,32.270541092],[26.155807956,32.496712464],[29.741779956,32.267220307],[29.901284019,31.608060461],[30.142504644,30.65063029],[30.32565981,30.620454299],[35.397082019,30.58676226],[35.413353894,31.418565363],[35.555465571,32.369863683],[36.475237935,32.561417901],[41.42712404,32.63858574],[42.478027873,32.398435638],[42.796874602,30.651645761],[45.248982665,30.588734729],[73.424315029,30.756977515],[73.476455102,30.900364923],[73.79575956,32.154256726],[76.565775081,32.3548249],[78.823192144,32.032183278],[79.177527435,31.821155861],[79.420787998,31.703311247],[79.629430477,30.863000732],[81.069644873,30.715799806],[88.209113915, 30.760053482],[94.874309394,30.809655445],[95.256960394,31.153915905],[95.348627935,32.316088051],[95.732289644,32.662290553],[96.834911581,33.002602901],[101.039886873,33.078426393],[105.800632685,32.812778133],[105.992886873,31.821155067],[106.310632935,30.806974157],[109.764940331,30.754592747],[113.267949581,30.848163429],[113.430832373,31.945005193],[113.66032931,33.151700625],[114.151581185,33.499009085],[118.347695581,33.180682552],[118.999120915,33.345836249],[119.429895323,33.582717722],[121.258016998,33.627192027],[125.987736115,33.082064943],[128.677264394,33.32659972],[130.413269727,33.327816803],[130.711947599,32.902689463],[130.947558727,30.639914137],[131.879616688,30.530882694],[145.624313727,30.419712559],[145.968377894,30.251379099],[146.81375604,29.301222324],[146.975048685,25.749281576],[146.932612165,14.07258182],[146.548733498,12.437844034],[144.773969352,10.885523685],[144.457490644,10.784860318],[137.418108185,10.666983161],[135.149493956,10.766485007],[123.104480581,11.262713656],[123.008288665,11.032489132],[122.016794373,10.669668681],[117.803886873,9.924549157],[115.200603831,8.531089391],[113.503830253,7.029560903],[112.051091144,5.298386666],[110.667928852,2.920150458],[109.77022406,1.483402217],[108.550222373,1.22922232],[106.39267229,2.37723873],[104.947840915,3.810378054],[104.33168454,4.338092117],[103.846324935,4.061838035],[99.852497727,2.346070815],[97.517155581,1.760928945],[92.438131894,1.229079445],[92.099573706,1.128138265],[91.011567352,0.896233638],[88.642863894,0.797213333],[17.848700915,0.456482943],[13.378192435,0.627014826],[10.648848665,0.668136364],[9.781436019,0.527872813],[7.26515856,0.768617169],[6.985475456,0.383166907],[6.372171819,0],[5.872315165,0.068585286],[5.872285531,0.068569411] ]

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

def drawWiimote(xy,height,sightsMM):
    canvas.delete("wiimote")
    x0 = xy[0]
    y0 = xy[1]
    scale = height/WIIMOTE_LENGTH
    coordinates = []
    for y,x in WIIMOTE:
        coordinates.append(x0+(x)*scale)
        coordinates.append(y0+(WIIMOTE_LENGTH-y)*scale)
    canvas.create_polygon(*coordinates,fill="white",width=0,tags="wiimote")
    if sightsMM:
        canvas.create_polygon(x0+SIGHT_OFFSET_X*scale,y0+SIGHT_OFFSET_Y1*scale,
            x0+(SIGHT_OFFSET_X+sightsMM)*scale,y0+SIGHT_OFFSET_Y1*scale,
            x0+SIGHT_OFFSET_X*scale,y0+(SIGHT_OFFSET_Y1+sightsMM)*scale,width=0,tags="wiimote",fill="red")
        canvas.create_polygon(x0+SIGHT_OFFSET_X*scale,y0+SIGHT_OFFSET_Y2*scale,
            x0+(SIGHT_OFFSET_X+sightsMM)*scale,y0+SIGHT_OFFSET_Y2*scale,
            x0+SIGHT_OFFSET_X*scale,y0+(SIGHT_OFFSET_Y2-sightsMM)*scale,width=0,tags="wiimote",fill="red")
        
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
    
def drawStatusBar():
    canvas.create_rectangle(0,int(WINDOW_SIZE[1]*(1-FONT_SIZE*2.6)),WINDOW_SIZE[0],WINDOW_SIZE[1],fill=rgb(VERY_DARK_GREEN),width=0,tags="statusBar")
    
def labelStatusBar(left=None,center=None,right=None):
    if left is not None:
        canvas.delete("statusBarLeft")
        canvas.create_text(5,WINDOW_SIZE[1]-5,text=left,fill="white",font=MYFONT,anchor="sw",tags="statusBarLeft")
    if center is not None:
        canvas.delete("statusBarCenter")
        canvas.create_text(WINDOW_SIZE[0]//2,WINDOW_SIZE[1]-5,text=center,fill="white",font=MYFONT,anchor="s",tags="statusBarCenter")
    if right is not None:
        canvas.delete("statusBarRight")
        canvas.create_text(WINDOW_SIZE[0]-5,WINDOW_SIZE[1]-5,text=right,fill="white",font=MYFONT,anchor="se",tags="statusBarLeft")
    
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
    
def drawCameraCross(xy,color=BLACK,tag="cameraCross"):
    x = int(cameraViewCenter[0] + ((xy[0]-512.) / 768.)* cameraViewHeight)
    y = int(cameraViewCenter[1] + ((384.-xy[1]) / 768.) * cameraViewHeight)
    thickness=3
    size=0.2
    l = size*WINDOW_SIZE[1]/2.
    t = thickness*PXSCALE
    c = rgb(color)
    canvas.delete(tag)
    canvas.create_rectangle(x-l//2,y-t//2,x-l//2+l,y-t//2+t,width=0,fill=c,tags=tag)
    canvas.create_rectangle(x-t//2,y-l//2,x-t//2+t,y-l//2+l,width=0,fill=c,tags=tag)
    
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
    drawWiimote((800,10),500,6)
    while running:
        update()
        time.sleep(0.01)
        
