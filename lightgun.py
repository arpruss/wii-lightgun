#!/usr/bin/python3
import wiimote
import myinput
import time
import math
import os
import pygame
import sys
import numpy as np
import atexit
import threading
import argparse
import subprocess
import cv2
from scipy.spatial.transform import Rotation

USE_P3P = False # fallback to P3P if only three points are visible; otherwise fallback to P2P with assumption about
               # gun being centered on screen
P3P_PROXIMITY_PREFERENCE = False # choose the solution closest to the last solution; otherwise, use acceleration data to choose the best solution
USE_P2PA = False # fallback to P2PA if only bottom markers or only top markers are visible; ensure markers are equal height
# P2PA is the Section 7 algorithm in https://link.springer.com/article/10.1007/s10851-026-01341-6
NUM_POINTS = 4
USE_CALIBRATION_HOMOGRAPHY = False

abortConnect = False

CONFIG_DIR = os.sep.join((os.path.expanduser("~"),".wiilightgun"))
LED_FILE = os.sep.join((os.path.expanduser("~"),".wiilightgun","irledcoordinates"))
SCREENSHOT_FILE = os.sep.join((os.path.expanduser("~"),".wiilightgun","screenshot"))
CALIBRATION_FILE = os.sep.join((os.path.expanduser("~"),".wiilightgun","wiimotecalibration"))
BLACK = (0,0,0)
WHITE = (255,255,255)
RED = (255,0,0)
GRAY = (64,64,64)
DARK_GREEN = (0,64,0)
VERY_DARK_GREEN = (0,32,0)
MYFONT = None
WINDOW_SIZE = None
PXSCALE = 1
ACCEL_FILTER_TIME = 0.25
ACCEL_CUTOFF_FREQ = 12
PYGAME_MODE = True
RUMBLE_TIME = 0.06
wm = None
running = True
crash = False
WIIMOTE_EVENT = threading.Event()
CONNECTED_EVENT = threading.Event()
DISCONNECT_DETECT_TIME = 4
lastMessage = 0
LONG_PRESS_TIME = 0.75
FONT_SIZE = 0.05
TEXT_SPACING = 1.3*FONT_SIZE
REPEAT_DELAY = 0.75
REPEAT_TIME = 0.05
CENTER_X = 1024/2
CENTER_Y = 768/2
NUNCHUK_SHIFT = 16
NUNCHUK_C = wiimote.NUNCHUK_BTN_C << NUNCHUK_SHIFT
NUNCHUK_Z = wiimote.NUNCHUK_BTN_Z << NUNCHUK_SHIFT
NUNCHUK_DEADZONE = 40
NUNCHUK_HYSTERESIS = 10
ASPECT_RATIO = 1920./1080
#CAMERA_ASPECT_RATIO = 1363./768
FOCAL_LENGTH_PIXELS = 1363.4 # 1363.4, 1634.5??
CAMERA_HEIGHT_PIXELS = 768

DEFAULT_IR_CALIBRATION = [(127,93),(896,93),(896,674),(127,674)]
CALIBRATION_CORNERS = ((0.125,0.05), (0.875,0.05), (0.875,0.95), (0.125,0.95))
UNIT_SQUARE = ((0,0), (1,0), (1,1), (0,1))

lastAngle = math.pi / 2
lastAccel = [0,0,1]
lastAccelTime = -1
lastQuad = None
    

# For moderate angles, the simple y correction (sightline parallax) is about half a pixel
# off and should be a bit faster as it punts more of the computation to cv2. But I haven't
# really tested the speed.
SIMPLE_Y_CORRECTION = False

verticalMap = ((wiimote.BTN_B, myinput.BTN_LEFT),
        (wiimote.BTN_A, myinput.BTN_RIGHT),
        (wiimote.BTN_1, myinput.KEY_Z),
        (wiimote.BTN_2, myinput.KEY_X),
        (NUNCHUK_Z, myinput.KEY_S),
        (NUNCHUK_C, myinput.KEY_A),
        (wiimote.BTN_PLUS, myinput.KEY_SPACE),
        (wiimote.BTN_HOME, myinput.KEY_ENTER),
        (wiimote.BTN_DOWN, myinput.KEY_DOWN),
        (wiimote.BTN_UP, myinput.KEY_UP),
        (wiimote.BTN_LEFT, myinput.KEY_LEFT),
        (wiimote.BTN_RIGHT, myinput.KEY_RIGHT))

minusVerticalMap = ((wiimote.BTN_DOWN, myinput.KEY_F6),
        (wiimote.BTN_UP, myinput.KEY_F7),
        (wiimote.BTN_LEFT, myinput.KEY_F4),
        (wiimote.BTN_RIGHT, myinput.KEY_F2),
        (wiimote.BTN_A, myinput.KEY_F1),
        (wiimote.BTN_B, myinput.KEY_TAB),
        (wiimote.BTN_HOME, myinput.KEY_F2),
        (wiimote.BTN_1, myinput.KEY_LEFTBRACE),
        (wiimote.BTN_2, myinput.KEY_RIGHTBRACE))
       
horizontalMap = (
        (wiimote.BTN_B, myinput.KEY_S),
        (wiimote.BTN_A, myinput.KEY_A),
        (wiimote.BTN_1, myinput.KEY_Z),
        (wiimote.BTN_2, myinput.KEY_X),
        (NUNCHUK_Z, myinput.KEY_S),
        (NUNCHUK_C, myinput.KEY_A),
        (wiimote.BTN_HOME, myinput.KEY_ENTER),
        (wiimote.BTN_PLUS, myinput.KEY_Q),
        (wiimote.BTN_DOWN, myinput.KEY_RIGHT),
        (wiimote.BTN_UP, myinput.KEY_LEFT),
        (wiimote.BTN_LEFT, myinput.KEY_DOWN),
        (wiimote.BTN_RIGHT, myinput.KEY_UP))

minusHorizontalMap = (
        (wiimote.BTN_DOWN, myinput.KEY_F2),
        (wiimote.BTN_UP, myinput.KEY_F4),
        (wiimote.BTN_LEFT, myinput.KEY_F6),
        (wiimote.BTN_RIGHT, myinput.KEY_F7),
        (wiimote.BTN_A, myinput.KEY_F1),
        (wiimote.BTN_B, myinput.KEY_TAB),
        (wiimote.BTN_HOME, myinput.KEY_F2),
        (wiimote.BTN_1, myinput.KEY_LEFTBRACE),
        (wiimote.BTN_2, myinput.KEY_RIGHTBRACE))

class Config():
    def __init__(self):
        self.center = {}
        try:
            with open(CALIBRATION_FILE) as f:
                for line in f:
                    try:
                        a,d = line.strip().split(maxsplit=2)
                        self.center[a] = tuple(map(float,d.split(",")))
                    except:
                        pass
        except:
            pass
            
        self.aspect = 1920./1080.
        self.ledLocations = None
        self.yCorrection = 0
        self.ledOffset = 0 # currently only works with USE_P2PA mode
        try:
            with open(LED_FILE) as f:
                s = tuple(map(float,f.readline().strip().split(",")))
                ledLocations = [ [0,0] for i in range(4) ]
                for i in range(4):
                    line = f.readline().strip().split(",")
                    for j in range(2):
                        ledLocations[i][j]=float(line[j])/s[j]
                if math.isnan(ledLocations[2][0]):  
                    NUM_POINTS = 2
                self.ledLocations = ledLocations
                try:
                    for line in f:
                        l = line.strip().split()
                        if l[0].lower() == "ycorrection":
                            self.yCorrection = float(l[1])/s[1]
                        elif l[0].lower() == "aspect":
                            self.aspect = float(l[1])
                        elif l[0].lower() == "offset":
                            self.ledOffset = float(l[1])/s[1]
                except:
                    pass
        except Exception as e:
            pass

    def haveCenter(self,wm):
        return wm.id in self.center

    def setLEDLocations(self,loc,size=(1.,1.)):
        self.ledLocations = [[loc[i][0]/size[0],loc[i][1]/size[1]] for i in range(4)]
            
    def getCenter(self,wm):
        return self.center.get(wm.id, (1024/2.,768/2.))
        
    def setCenter(self,wm,c):
        self.center[wm.id] = c
        
    def saveCalibration(self):
        with open(CALIBRATION_FILE, "w") as f:
            for a in self.center:
                f.write("%s %g,%g\n" % (a,self.center[a][0],self.center[a][1]))
                
    def saveLEDs(self):
        if self.ledLocations:
            with open(LED_FILE, "w") as f:
                f.write("1,1\n")
                if i in range(NUM_POINTS):
                    l = self.ledLocations[i]
                    f.write("%g,%g\n" % tuple(l))
                if NUM_POINTS == 2:
                    f.write("NaN,NaN\nNaN,NaN\n")
                f.write("ycorrection %g\n" % self.yCorrection)
                f.write("aspect %g\n" % self.aspect)

            
    def pointerPosition(self,irQuad):
        valid = []
        for i in range(4):
            if irQuad[i] is not None:
                valid.append(i)
        if len(valid) == 2:
            return pointerPosition2LED(irQuad[valid[0]],irQuad[valid[1]],CONFIG.ledLocations[valid[0]],CONFIG.ledLocations[valid[1]],lastAccel if USE_P2PA else None)
        if len(valid) != 4:
            return None
    
        h = Homography(irQuad,self.ledLocations)
        if self.yCorrection: # sightline parallax correction
            if SIMPLE_Y_CORRECTION:
                xy = h.apply((0,0))
                xy2 = h.apply((0.01,0.01)) # shouldn't this be (0,0.01)?
                dx,dy = (xy2[0]-xy[0])*self.aspect,xy2[1]-xy[1]
                d = math.hypot(dx,dy)
                return xy[0]+self.yCorrection*dx/d/self.aspect,xy[1]+self.yCorrection*dy/d
            else:
                return h.apply((0,self.yCorrection/h.minimumScalingAtOrigin(self.aspect))) 
        else:
            return h.apply((0,0))

            
class FakeWiimote():
    def __init__(self):
        self.state = { "acc":(128,128,128), "buttons":0, "ir_src":[], "fake":True }

def cosAngle(a,b):
    return math.cos( math.atan2(b[1],b[0])-math.atan2(a[1],a[0]) )

def solutionToXYZ(m1,m2,d1,d2,h1,h2): 
    # assume camera y-coordinate is < marker y-coordinate
    # assume equal heights
    if m1[0]>m2[0]:
        m1,m2,d1,d2,h1,h2 = m2,m1,d2,d1,h2,h1
    # https://npworld.wolfram.com/Circle-CircleIntersection.html with R=d1 and r=d2
    d = math.hypot(m2[1]-m1[1],m2[0]-m1[0])
    x = m1[0]+(d*d-d2*d2+d1*d1)/(2*d) # magnitude of vector from m1 to intersection    
    y = m1[1]-math.sqrt(4*d*d*d1*d1-(d*d-d2*d2+d1*d1)**2)/(2*d)
    z = h1 + m1[2]
    return np.array([x,y,z])
    
def computeP2PA(m1,m2,cos_beta,rho1,rho2):
    # assume equal heights
    i_is_1 = rho1 != math.pi/2
    if i_is_1:
        rho_i = rho1
        rho_j = rho2
    else:
        rho_i = rho2
        rho_j = rho1
    cot_j = 1/math.tan(rho_j)
    tan_i = math.tan(rho_i)
    cottan = cot_j * tan_i
    a = 1-2*cos_beta*cottan + cottan*cottan
    d = math.hypot(m2[1]-m1[1],m2[0]-m1[0])
    dj = d/math.sqrt(a)
    di = dj*cot_j*tan_i
    hj = -dj * cot_j
    hi = hj

    if i_is_1:
        return (di,dj,hi,hj)
    else:
        return (dj,di,hj,hi)

def n(v):
    return np.array(v) / np.linalg.norm(v)
    
def cross2D(p,q):
    return p[0]*q[1]-p[1]*q[0]
        
def pointerPosition2LED(p1,p2,led1,led2,g):
    # if g is non-zero, use P2PA
    dir1Orig = np.array([ (p1[0])*CAMERA_HEIGHT_PIXELS,FOCAL_LENGTH_PIXELS,(p1[1])*CAMERA_HEIGHT_PIXELS])
    dir2Orig = np.array([ (p2[0])*CAMERA_HEIGHT_PIXELS,FOCAL_LENGTH_PIXELS,(p2[1])*CAMERA_HEIGHT_PIXELS])
    avgHeight = (led1[1]+led2[1])/2
    m1 = (led1[0]*CONFIG.aspect,CONFIG.ledOffset,avgHeight)
    m2 = (led2[0]*CONFIG.aspect,CONFIG.ledOffset,avgHeight)
    
    if g is not None:
        down = np.array([0.,0.,-1.])
        g = -n(g)
        prod = np.cross(g,down)
        accelerometerRotation = Rotation.align_vectors( [down,prod],[g,prod] )[0].as_matrix()

        # accelerometerRotation.dot(g) should equal down
        dir1 = accelerometerRotation.dot(dir1Orig)
        dir2 = accelerometerRotation.dot(dir2Orig)
        d1 = math.hypot(dir1[0],dir1[1])
        d2 = math.hypot(dir2[0],dir2[1])
        h1 = -dir1[2]
        h2 = -dir2[2]
        
        cos_beta = cosAngle((dir1[0],dir1[1]),(dir2[0],dir2[1]))
        rho1 = math.pi-math.atan2(d1,h1)
        rho2 = math.pi-math.atan2(d2,h2)

        cameraPosition = solutionToXYZ(m1,m2,*computeP2PA(m1,m2,cos_beta,rho1,rho2))
    else:
        # Assume gun lies on the ray coming out of the center of the screen.
        # This assumption appears good enough for practical purposes even if the user is aligned
        # with the edge of the TV, for a typical viewing distance.
        rayAngle = math.acos(dir1Orig.dot(dir2Orig) / (np.linalg.norm(dir1Orig) * np.linalg.norm(dir2Orig)))
        cameraDistanceFromLEDMidpoint = abs(led1[0]-led2[0]) * CONFIG.aspect / (2. * math.tan(rayAngle / 2))
        cameraDistanceFromTVCenter = math.sqrt(cameraDistanceFromLEDMidpoint*cameraDistanceFromLEDMidpoint-avgHeight*avgHeight)
        
        cameraPosition = np.array([CONFIG.aspect*.5,-cameraDistanceFromTVCenter,.5])
    
    dir1Obj = m1 - cameraPosition
    dir2Obj = m2 - cameraPosition
    
    cameraToObjectRotation = Rotation.align_vectors( [n(dir1Obj),n(dir2Obj)], [n(dir1Orig), n(dir2Orig)] )[0].as_matrix()
    
    cameraPointing = cameraToObjectRotation.dot( np.array((0.,1.,0.)) )
    yCorrection = cameraToObjectRotation.dot( np.array((0.,0.,CONFIG.yCorrection)) )
    cameraPosition += yCorrection

    dy = -cameraPosition[1]
    t = dy / cameraPointing[1]
    
    x = cameraPosition[0] + t * cameraPointing[0]
    z = cameraPosition[2] + t * cameraPointing[2]

    return (x/CONFIG.aspect,z)

# find a local minimum        
def minimize(f,a,b,n=4):
    fa = f(a)
    fb = f(b)
    fab = fa
    while n>0:
        ab = 0.5*(a+b)
        fab = f(ab)
        if fa<fb:
            fb=fab
            b=ab
        else:
            fa=fab
            a=ab
        n-=1
    if fa<fb:
        return fa,a
    else:
        return fb,b

def getButtons(state):
    b = state['buttons']
    if 'nunchuk' in state:
        return b | state['nunchuk']['buttons'] << NUNCHUK_SHIFT
    else:
        return b

def wiimoteWait(timeout=None):
    if isinstance(wm, FakeWiimote):
        time.sleep(1)
        return

    WIIMOTE_EVENT.wait(timeout if timeout is not None and timeout < DISCONNECT_DETECT_TIME else DISCONNECT_DETECT_TIME)
    if time.monotonic() > lastMessage + DISCONNECT_DETECT_TIME:
        print("Disconnect detected")
        connect(silent=True)
        CONNECTED_EVENT.wait()
        if crash:
            sys.exit(0)
        print("Reconnected")
    WIIMOTE_EVENT.clear()
    
def wiimoteCallback(events,t):
    global lastMessage
    lastMessage = time.monotonic()
    WIIMOTE_EVENT.set()

# was 1280
INTRINSIC = np.array( ( [FOCAL_LENGTH_PIXELS/768.,0,0.0],
    [0,FOCAL_LENGTH_PIXELS/768.,0.0],
    [0,0,1] ), dtype=np.float64 )

class Homography:
    def __init__(self,input,output):
        if input is None: # identity
            self.matrix = None
            return
        self.matrix,_ = cv2.findHomography(np.float64(input),np.float64(output))

    #def jacobianAtOrigin(self):
    #    return np.array( (self.a-self.c*self.g, self.b-self.c*self.h),
    #                     (self.d-self.f*self.g, self.e-self.f*self.h) )

    def minimumScalingAtOrigin(self, aspect):
        if self.matrix is None:
            return 1.
        # This measures the lowest scaling between camera and screen coordinates.
        # This should correspond to the correct conversion between camera and screen coordinates 
        # for y adjustment (sightline parallax).
        #
        # Equals the smallest singular value of the Jacobian at the origin
        # ( https://lucidar.me/en/mathematics/singular-value-decomposition-of-a-2x2-matrix/ )

        A = aspect*(self.matrix[0][0]-self.matrix[0][2]*self.matrix[2][0])
        B = aspect*(self.matrix[0][1]-self.matrix[0][2]*self.matrix[2][1])
        C = self.matrix[1][0]-self.matrix[1][2]*self.matrix[2][0]
        D = self.matrix[1][1]-self.matrix[1][2]*self.matrix[2][1]
        
        S1 = A*A+B*B+C*C+D*D
        u = A*A+B*B-C*C-D*D
        v = A*C+B*D
        S2 = math.sqrt(u*u+v*v)
        return math.sqrt((S1-S2)/2.)

    def apply(self,xy):
        if self.matrix is None:
            return xy
        out = cv2.perspectiveTransform(np.array(((xy,),),dtype=np.float64),self.matrix)
        return out[0][0]

    def __repr__(self):
        return repr(self.matrix)

def drawText(s,x=0.5,y=0.5,color=WHITE):
    text = MYFONT.render(s, True, color)
    textRect = text.get_rect()
    textRect.center = (WINDOW_SIZE[0]*x,WINDOW_SIZE[1]*y)
    surface.blit(text, textRect)

def drawBlob(xy,size=3,color=WHITE):
    pygame.draw.rect(surface, color, (xy[0]*WINDOW_SIZE[0]-size*PXSCALE/2, (1.-xy[1])*WINDOW_SIZE[1]-size*PXSCALE/2, size*PXSCALE, size*PXSCALE))

def drawCross(xy,thickness=3,size=0.25,color=WHITE):
    l = size*WINDOW_SIZE[1]/2.
    x = xy[0]*WINDOW_SIZE[0]
    y = (1-xy[1])*WINDOW_SIZE[1]
    t = thickness*PXSCALE
    pygame.draw.rect(surface, color, (x-l/2.,y-t/2.,l,t))
    pygame.draw.rect(surface, color, (x-t/2.,y-l/2.,t,l))

def showPoints(ir,irQuad):
    cy = int(WINDOW_SIZE[1] * 0.25)
    cx = WINDOW_SIZE[0] // 2
    height = int(WINDOW_SIZE[1] * 0.4)
    width = height * 4 // 3
    
    pygame.draw.rect(surface, VERY_DARK_GREEN, (cx-width//2, cy-height//2, width, height))

    rawPoints = [getPoint(p) for p in ir if p is not None]

    if irQuad:
        for i in range(len(irQuad)):
            xy = irQuad[i]
            if xy is None:
                continue
            x = int(cx + xy[0] * height)
            y = int(cy + (-xy[1]) * height)
            text = MYFONT.render(str(i+1), True, RED if (tuple(xy) in rawPoints) else GRAY)
            textRect = text.get_rect()
            textRect.center = (x,y)
            surface.blit(text, textRect)
    for point in ir:
        if point is not None:
            xy = getPoint(point)
            size = getSize(point)
            x = int(cx + xy[0] * height)
            y = int(cy + (-xy[1]) * height)
            pygame.draw.rect(surface, WHITE, (x-size*PXSCALE/2, y-size*PXSCALE/2, size*PXSCALE, size*PXSCALE))
    
def getPoint(p):
    xy = calibrationHomography.apply((p[0][0],p[0][1]))
    return (xy[0]-CENTER_X)/768., (xy[1]-CENTER_Y)/768.
    
def getSize(p):
    try:
        return p[1]
    except:
        return p.get('size',1)
    
def updateAcceleration(state):
    global lastAngle,lastAccel,lastAccelTime

    a = list(state.get("acc_calib",(0.,0.,1.)))
    
    mag = math.sqrt(a[0]*a[0]+a[1]*a[1]+a[2]*a[2])
        
    t = time.monotonic()
    
    if .8 <= mag <= 1.2:
        if lastAccelTime >= 0:
            dt = min(max(t-lastAccelTime,.01),.1)
            alpha = math.exp(-2.0 * math.pi * ACCEL_CUTOFF_FREQ * dt)
            for i in range(3):
                a[i] = alpha * lastAccel[i] + (1-alpha) * a[i]

        lastAccel = a
        lastAccelTime = t
    else:
        lastAccelTime = t
        if lastAccelTime < 0:
            lastAccel = a

    try:
        lastAngle = math.atan2(lastAccel[2],lastAccel[0])
    except:
        pass

lastQuad = None

def absSlope(p1,p2):
    if p1[0] == p2[0]:
        return math.inf
    return abs((p2[1]-p1[1])/(p2[0]-p1[0]))

def identifyPoints(points):
    n = len(points)

    identified = [None for i in range(n)]
    
    if n<2:
        return identified

    rot = lastAngle-math.pi/2
    c = math.cos(rot)
    s = math.sin(rot)

    def rotate(p):
        x = p[0]
        y = p[1]
        return (x*c-y*s,x*s+y*c)
        
    rp = tuple(map(rotate, points))

    if n == 2:
        if absSlope(rp[0],rp[1]) < 0.75:
            # two co-horizontal points for P2PA
            if rp[0][1] < 0 and rp[1][1] < 0:
                if rp[0][0] < rp[1][0]:
                    identified[0] = 0
                    identified[1] = 1
                else:
                    identified[0] = 1
                    identified[1] = 0
            elif rp[0][1] > 0 and rp[1][1] > 0:
                if rp[0][0] < rp[1][0]:
                    identified[0] = 3
                    identified[1] = 2
                else:
                    identified[0] = 2
                    identified[1] = 3
            # the diagonal case typically does not have a 
    else:
        cx = sum(p[0] for p in points)/float(n)
        cy = sum(p[1] for p in points)/float(n)
        
        ordered = list(range(n))
        ordered.sort( key=lambda i: math.atan2(points[i][1]-cy,points[i][0]-cx) )
        
        if n == 4:
            # check for convexity
            for i in range(4):
                j = (i+1)%4
                k = (i+2)%4
                p = (points[ordered[j]][0]-points[ordered[i]][0],points[ordered[j]][1]-points[ordered[i]][1])
                q = (points[ordered[k]][0]-points[ordered[j]][0],points[ordered[k]][1]-points[ordered[j]][1])
                if cross2D(p,q) <= 0:
                    # failure!
                    return identified

        # find the most horizontal line
        minSlope = math.inf
        minSlopeIndex = 0
        for i in range(n):
            j = (i+1)%n
            slope = absSlope(rp[ordered[i]],rp[ordered[j]])
            if slope < minSlope:
                minSlope = slope
                minSlopeIndex = i

        i = minSlopeIndex
        j = (minSlopeIndex+1)%n
        k = (minSlopeIndex+2)%n
        if n == 4:
            l = (minSlopeIndex+3)%n
            if rp[ordered[j]][0] < rp[ordered[i]][0]:
                # right to left, so ij is upper line
                identified[ordered[i]] = 2
                identified[ordered[j]] = 3
                if 2 * rp[ordered[k]][0] < (rp[ordered[j]][0] + rp[ordered[i]][0]):
                    # k is to the left of the middle of the upper line segment, so
                    # assume it's the point 0
                    identified[ordered[k]] = 0
                    identified[ordered[l]] = 1
                else:
                    # now assume it's point 1
                    identified[ordered[k]] = 1
                    identified[ordered[l]] = 0
            else:
                # left to right, so ij is lower line
                identified[ordered[i]] = 0
                identified[ordered[j]] = 1
                if 2 * rp[ordered[k]][0] < (rp[ordered[j]][0] + rp[ordered[i]][0]):
                    # k is to the left of the middle of the lower line segment, so it's3
                    identified[ordered[k]] = 3
                    identified[ordered[l]] = 2
                else:
                    identified[ordered[k]] = 2
                    identified[ordered[l]] = 3                
        else:
            # n == 3
            if rp[ordered[j]][0] < rp[ordered[i]][0]:
                # right to left, so ij is upper line
                identified[ordered[i]] = 2
                identified[ordered[j]] = 3
                if 2 * rp[ordered[k]][0] < (rp[ordered[j]][0] + rp[ordered[i]][0]):
                    # k is to the left of the middle of the upper line segment, so
                    # assume it's the point 0
                    identified[ordered[k]] = 0
                else:
                    # now assume it's point 1
                    identified[ordered[k]] = 1
            else:
                # left to right, so ij is lower line
                identified[ordered[i]] = 0
                identified[ordered[j]] = 1
                if 2 * rp[ordered[k]][0] < (rp[ordered[j]][0] + rp[ordered[i]][0]):
                    # k is to the left of the middle of the lower line segment, so it's3
                    identified[ordered[k]] = 3
                else:
                    identified[ordered[k]] = 2
    return identified

def points3To4(points):
    if CONFIG.ledLocations is None:
        return None

    identified = identifyPoints(points)
    if None in identified:
        return None

    missing = tuple(set((0,1,2,3)) - set(identified))[0]

    def fix(p):
        return (p[0]*CONFIG.aspect,p[1],0)

    source = np.array([fix(CONFIG.ledLocations[identified[i]]) for i in range(3)],dtype=np.float64)
    dest = np.array(points,dtype=np.float64)
    retval, rvecs, tvecs = cv2.solveP3P(source,dest,INTRINSIC,None,cv2.SOLVEPNP_AP3P) # AP3P

    if not rvecs:
        return None

    bestR2 = math.inf
    missingLED = np.float64((fix(CONFIG.ledLocations[missing]),))

    if lastQuad is None or not P3P_PROXIMITY_PREFERENCE:
        accel = np.float64((-lastAccel[0],lastAccel[2],lastAccel[1]))
        base = np.float64((0,math.sqrt(accel[0]*accel[0]+accel[1]*accel[1]+accel[2]*accel[2]),0))
        best = None
        bestR2 = None
        for i in range(len(rvecs)):
            if not np.isnan(tvecs[i][0]):
                #rotationMatrix = np.linalg.inv(cv2.Rodrigues(rvecs[i])[0])
                rotationMatrix = cv2.Rodrigues(rvecs[i])[0]
                delta = rotationMatrix.dot(base) - accel
                r2 = delta[0]*delta[0]+delta[1]*delta[1]+delta[2]*delta[2]
                if best is None or r2 < bestR2:
                    best = i
                    bestR2 = r2

        if best is None:
            return None

        proj = cv2.projectPoints(missingLED,rvecs[best],tvecs[best],INTRINSIC,None)[0][0][0]
    else:
        bestProj = None
        for i in range(len(rvecs)):
            if not np.isnan(tvecs[i][0]):
                proj = cv2.projectPoints(missingLED,rvecs[i],tvecs[i],INTRINSIC,None)[0][0][0]
                r2 = math.hypot(proj[0]-lastQuad[missing][0],proj[1]-lastQuad[missing][1])
                if r2 < bestR2:
                    bestProj = proj
                    bestR2 = r2
        if bestProj is None:
            return None
        proj = bestProj

    out = [None,None,None,None]
    for i in range(4):
        if i == missing:
            out[i] = proj
        else:
            out[i] = points[identified.index(i)]

    return out
    
def dist2DSquared(xy1,xy2):
    dx = xy1[0]-xy2[0]
    dy = xy1[1]-xy2[1]
    return dx*dx+dy*dy
    
def getIRQuad(ir):
    global lastQuad

    if ir is None:
        return None

    # get the IR LED quad, normalized and arranged counterclockwise from lower left
    
    points = [getPoint(p) for p in ir if p is not None]

    count = len(points)

    if count < 2:
        return None
        
    if NUM_POINTS == 2:
        identified = identifyPoints(points)
        if count == 2 or count == 3:
            if 0 in identified and 1 in identified:
                lastQuad = [points[identified.index(0)],points[identified.index(1)],None,None]
            elif 2 in identified and 3 in identified:
                lastQuad = [points[identified.index(2)],points[identified.index(3)],None,None]
            else:
                lastQuad = None
        elif count == 4:
            if CONFIG.ledLocations[0][1] < .5:
                # LEDs are on bottom
                lastQuad = [points[identified.index(0)],points[identified.index(1)],None,None]
            else:
                # or on top
                lastQuad = [points[identified.index(3)],points[identified.index(2)],None,None]
        else:
            lastQuad = none # should not happen
    elif count == 2 or (count == 3 and not USE_P3P):
        identified = identifyPoints(points)
        if 0 in identified and 1 in identified:
            p0 = points[identified.index(0)]
            p1 = points[identified.index(1)]
            if not lastQuad or not lastQuad[2] or not lastQuad[3]:
                lastQuad = [p0,p1,None,None]
            else:
                if not lastQuad[0] or not lastQuad[1]:
                    lastQuad = [None,None,p1,p0]
                else:
                    dCurrent = dist2DSquared(p0,lastQuad[0])+dist2DSquared(p1,lastQuad[1])
                    dRev = dist2DSquared(p0,lastQuad[3])+dist2DSquared(p1,lastQuad[2])
                    if dCurrent > 1.25*dRev:
                        lastQuad = [None,None,p1,p0]
                    else:
                        lastQuad = [p0,p1,None,None]
        elif 2 in identified and 3 in identified:
            p2 = points[identified.index(2)]
            p3 = points[identified.index(3)]
            if not lastQuad or not lastQuad[0] or not lastQuad[1]:
                lastQuad = [None,None,p2,p3]
            else:
                if not lastQuad[2] or not lastQuad[3]:
                    lastQuad = [p3,p2,None,None]
                else:
                    dCurrent = dist2DSquared(p2,lastQuad[2])+dist2DSquared(p3,lastQuad[3])
                    dRev = dist2DSquared(p2,lastQuad[1])+dist2DSquared(p3,lastQuad[0])
                    if dCurrent > 1.25*dRev:
                        lastQuad = [p3,p2,None,None]
                    else:
                        lastQuad = [None,None,p2,p3]
        else:
            lastQuad = None
    elif count !=3 and count != 4:
        lastQuad = None
    elif count == 3: # USE_P3P
        points = points3To4(points)
        if points is None:
            lastQuad = None
        else:
            lastQuad = points
    else:
        identified = identifyPoints(points)
        if None in identified:
            lastQuad = None
        else:
            lastQuad = [points[identified.index(i)] for i in range(4)]
    return lastQuad
    
def getDisplaySize():
    info = pygame.display.Info()
    return info.current_w, info.current_h    

def screenshot():
    size = getDisplaySize()
    img = pygame.Surface(size)
    img.blit(surface,(0,0),((0,0),size))
    pygame.image.save(img,SCREENSHOT_FILE+str(time.monotonic())+".png")
    
def checkQuitAndKeys():
    global running
    pygame.event.pump()
    keys = set()
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            running = False
            sys.exit(0)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F8:
                screenshot()
            keys.add(event.key)
    if wm and 'buttons' in wm.state:
        if wm.state['buttons'] & wiimote.BTN_HOME:
            running = False
            sys.exit(0)
    return keys
    
def verticalArrow(xy,length,color=WHITE):
    x,y = xy
    pygame.draw.line(surface,color,[x,y],[x,y+length],2)
    pygame.draw.line(surface,color,[x,y],[x-length//2,y+length//2],2)
    pygame.draw.line(surface,color,[x,y],[x+length//2,y+length//2],2)

def drawArrow(xy,bottom,color=WHITE):
    x,y = xy
    if bottom:
        length = -y
        edgeY = WINDOW_SIZE[1]-1
        signY = -1
    else:
        length = y-WINDOW_SIZE[1]
        edgeY = 0
        signY = 1
    verticalArrow((x,edgeY),length*signY,color=color)
    
def measure(flexible=False,screenWidth=1.):
    global running,surface
    
    size = WINDOW_SIZE
    scale = float(screenWidth)/WINDOW_SIZE[0]
    corner = 0

    ledPixel = [[int(size[0]*1./3),int(-0.1*size[1])],[int(size[0]*2./3),int(-0.1*size[1])],[int(size[0]*2./3),int(1.1*size[1])],[int(size[0]*1./3),int(1.1*size[1])]]

    if CONFIG.ledLocations:
        for i in range(4):
            for j in range(2):
                ledPixel[i][j] = int(math.floor(0.5+CONFIG.ledLocations[i][j]*size[j]))
    
    buttonMap = ((wiimote.BTN_LEFT,(-1,0)),(wiimote.BTN_RIGHT,(1,0)),(wiimote.BTN_UP,(0,1)),(wiimote.BTN_DOWN,(0,-1)))

    prevButtons = 0
    prevTime = time.monotonic()
    CONNECTED_EVENT.wait()
    if crash:
        sys.exit(0)
    
    if not CONFIG.haveCenter(wm):
        center()    
    
    nextRepeat = 0
    done = False
    yCorrection = int(math.floor(CONFIG.yCorrection*size[1] + 0.5))
    
    while running:
        time.sleep(0.005)
        checkQuitAndKeys()
        surface.fill(DARK_GREEN)
        updateAcceleration(wm.state)
        ir = wm.state.get("ir", [None,None,None,None])
        irQuad = getIRQuad(ir)
        
        showPoints(ir,irQuad)

        if irQuad:
            CONFIG.setLEDLocations(ledPixel,size)
            CONFIG.yCorrection = yCorrection / size[1]
            s = CONFIG.pointerPosition(irQuad)
            if s is not None:
                drawCross(s,color=RED)

        drawText("HOME: quit without saving", y=0.5+TEXT_SPACING*2)
        drawText("A: done", y=0.5+TEXT_SPACING*3)

        buttons = getButtons(wm.state)
        pressed = buttons &~ prevButtons
        released = ~buttons & prevButtons
        prevButtons = buttons

        move = (0,0)

        for wii,dir in buttonMap:
            if pressed & wii:
                nextRepeat = time.monotonic()+REPEAT_DELAY
                move = dir
                break
            elif buttons & wii and time.monotonic()>=nextRepeat:
                nextRepeat = time.monotonic()+REPEAT_TIME
                move = dir
                break

        if corner==4:
            yCorrection += move[1]

        for i in range(NUM_POINTS):
            xy = ledPixel[i]
            if NUM_POINTS > 2:
                bottom = UNIT_SQUARE[i][1] < 0.5
            else:
                bottom = xy[1] < .5
            if xy[1] > 0 and bottom:
                xy[1] = 0
            if xy[1] < WINDOW_SIZE[1]-1 and not bottom:
                xy[1] = WINDOW_SIZE[1]-1
            if xy[0] < 0:
                xy[0] = 0
            if xy[0] >= WINDOW_SIZE[0]:
                xy[0] = WINDOW_SIZE[0]-1
            if not flexible:
                ledPixel[i^1][1] = xy[1]
            if i == corner:
                xy[0] += move[0]
                xy[1] += move[1]
            x,y = xy
            if bottom:
                length = -y
                signY = 1
            else:
                length = y-size[1]
                signY = -1
            drawArrow(xy,bottom,color=WHITE if i==corner else GRAY)
        
        if corner<4:
            drawText("DPad: move LED location",y=0.5)
            drawText("-/+: next/previous setting",y=0.5+TEXT_SPACING)
            if NUM_POINTS == 2:
                drawText("1/2: LEDs on top/bottom",y=0.5+TEXT_SPACING*4)
            drawText("LED is %.4g units (%.1f px) off-screen" % (length*scale, length),y=0.5+TEXT_SPACING*(4 if NUM_POINTS==4 else 5))
        else:
            drawText("Up/Down: adjust Y correction",y=0.5)
            drawText("-/+: next/previous setting",y=0.6)
            drawText("Y correction is %.4g units (%.1f px)" % (yCorrection*scale, yCorrection),y=0.5+0.075*4)
            ax = int(size[0]//4)
            ay = int(size[1]*0.5-yCorrection/2)            
            b = min(size[1] * .2, yCorrection + size[1] * .1)
            pygame.draw.rect(surface, VERY_DARK_GREEN, ( [ax-b//2,ay+yCorrection//2-b//2,b,b] ))
            verticalArrow((ax,ay),yCorrection,color=WHITE)

        if pressed & wiimote.BTN_PLUS:
            corner = (corner+1) % 5
            if NUM_POINTS == 2 and corner == 2:
                    corner = 4
        elif pressed & wiimote.BTN_MINUS:
            corner = (corner-1) % 5
            if NUM_POINTS == 2 and corner == 3:
                corner = 1
        elif pressed & wiimote.BTN_1:
            if ledPixel[0][1] < .5*size[1]:
                ledPixel[0][1] = size[1]-ledPixel[0][1]
            if ledPixel[1][1] < .5*size[1]:
                ledPixel[1][1] = size[1]-ledPixel[1][1]
        elif pressed & wiimote.BTN_2:
            if ledPixel[0][1] > .5*size[1]:
                ledPixel[0][1] = size[1]-ledPixel[0][1]
            if ledPixel[1][1] > .5*size[1]:
                ledPixel[1][1] = size[1]-ledPixel[1][1]
        elif ( pressed & wiimote.BTN_A ):
            done = True
            break              
            
        pygame.display.flip()

    if not done:
        return False
        
    CONFIG.setLEDLocations(ledPixel,size)
    CONFIG.yCorrection = yCorrection / size[1]
    CONFIG.saveLEDs()
        
    return True
                
# compute location of LEDs in screen coordinates                
def computeLEDs(calibrationData,flexible):
    avg = [[0,0] for i in range(len(CALIBRATION_CORNERS))]
    
    for i in range(len(CALIBRATION_CORNERS)):
        for j in range(2):
            avg[i][j] = sum((c[j] for c in calibrationData[i])) / len(calibrationData[i])

    fromIRToScreen = Homography(avg,CALIBRATION_CORNERS)
    
    leds = list(list(fromIRToScreen.apply(p)) for p in UNIT_SQUARE)
    
    if not flexible:
        y = (leds[0][1]+leds[1][1])/2.
        leds[0][1] = y
        leds[1][1] = y
        y = (leds[2][1]+leds[3][1])/2.
        leds[2][1] = y
        leds[3][1] = y
        
    return leds

def calibrate(flexible=False):
    global CALIBRATION_CORNERS,running,surface

    if args.terminal:
        print("Calibration cannot work with terminal mode.")

    corner = 0
    calibrationData = tuple([] for i in range(len(CALIBRATION_CORNERS)))

    prevButtons = 0
        
    # coordinate systems: 
    #  IR: (0,0) is lower-left LED and (1,1) is upper-right LED
    #  screen: (0,0) is lower-left corner of screen and (1,1) is upper-right corner of screen
    #  calibrationData is in IR coordinates
    #  CALIBRATION_CORNERS is in screen coordinates
    
    CONNECTED_EVENT.wait()
    if crash:
        sys.exit(1)
    
    if not CONFIG.haveCenter(wm):
        center()

    lastCalibrated = time.monotonic()

    while running:
        wiimoteWait(0.25)
        ir = wm.state.get("ir", [None,None,None,None])
        buttons = getButtons(wm.state)
        newButtons = buttons & ~prevButtons
        prevButtons = buttons
        checkQuitAndKeys()
        surface.fill(BLACK)
        updateAcceleration(wm.state)
        irQuad = getIRQuad(ir)
        showPoints(ir,irQuad)
        debounced = 0.5 + lastCalibrated < time.monotonic()
        valid = irQuad and debounced
        drawCross(CALIBRATION_CORNERS[corner],color=RED if valid else GRAY)
        if debounced:
            drawText("Press trigger (B"+(" or C" if 'nunchuk' in wm.state else "")+") while pointing at red calibration mark" if irQuad else "Point Wiimote at calibration mark from far enough away")
        if newButtons & wiimote.BTN_MINUS and len(calibrationData[0]):
            if corner == 0:
                corner = len(CALIBRATION_CORNERS)-1
            else:
                corner -= 1
            if len(calibrationData[corner]):
                del calibrationData[corner][-1]
        elif newButtons & (wiimote.BTN_B | NUNCHUK_C) and valid:
            lastCalibrated = time.monotonic()
            z = irQuad.toUnitSquare((0.5,0.5))
            calibrationData[corner].append(z)
            corner = (corner + 1) % len(CALIBRATION_CORNERS)
        n = len(calibrationData[-1])
        if n:
            drawText("Each mark has been calibrated "+("once" if n==1 else "%d times" % n),y=0.7)
            drawText("Press A "+("or C " if 'nunchuk' in wm.state else "")+"button if that's enough",y=0.8)
            if newButtons & wiimote.BTN_A:
                break
            if not flexible:
                leds = computeLEDs(calibrationData,flexible)
                for i in range(4):
                   x = int(leds[i][0] * WINDOW_SIZE[0])
                   y = int((1-leds[i][1]) * WINDOW_SIZE[1])
        pygame.display.flip()
            
    if not running or not len(calibrationData[-1]):
        return False

    ledLocations = computeLEDs(calibrationData,flexible)
    
    CONFIG.ledLocations = ledLocations
    CONFIG.yCorrection = 0
    CONFIG.saveLEDs()
    
    return True


def center():
    CONNECTED_EVENT.wait()
    if crash:
        sys.exit(1)

    running = True

    quads = [None,None]

    while running:
        keys = checkQuitAndKeys()
        updateAcceleration(wm.state)
        surface.fill(BLACK)
        wiimoteWait(0.25)
        if quads[0] is None:
            drawText("Put Wiimote right-side-up pointing at LEDs")
            drawText("Ensure repeatable alignment", y=0.6)
            index = 0
        elif quads[1] is None:
            drawText("Put Wiimote upside-down pointing at LEDs")
            drawText("Ensure same alignment as before ", y=0.6)
            index = 1
        else:
            break
        ir = wm.state.get("ir",[None,None,None,None])
        irQuad = getIRQuad(ir)
        showPoints(ir,irQuad)
        #print(lastAngle, (1-index*2)*math.pi/2)
        if irQuad and abs(lastAngle - (1-index*2)*math.pi/2) < math.pi/4:
            drawText("Press C on Nunchuk or SPACE on keyboard", y=0.7)
            buttons = getButtons(wm.state)
            if buttons & NUNCHUK_C or pygame.K_SPACE in keys:
                quads[index] = irQuad
        pygame.display.flip()

    if not running:
        CENTER_X = 1024/2
        CENTER_Y = 768/2
        return

    sx = 0
    sy = 0

    for i in range(2): 
        for p in quads[0]:
            if p is not None:
                sx += p[0]
                sy += p[1]
            
    CENTER_X = sx / 8. * 1024.
    CENTER_Y = sy / 8. * 768.
    
    CONFIG.setCenter(wm, (CENTER_X, CENTER_Y))
    CONFIG.saveCalibration()

def demo():
    CONNECTED_EVENT.wait()
    if crash:
        sys.exit(1)

    running = True

    while running:
        wiimoteWait(0.25)
        surface.fill(BLACK)
        drawText("Press HOME to exit")
        buttons = getButtons(wm.state)
        ir = wm.state.get("ir",[None,None,None,None])
        checkQuitAndKeys()
        updateAcceleration(wm.state)
        irQuad = getIRQuad(ir)
        showPoints(ir,irQuad)
        if irQuad:
            screenXY = CONFIG.pointerPosition(irQuad)
            if screenXY is not None:
                drawCross(screenXY,color=RED)
        pygame.display.flip()

    pygame.quit()

def emulateMouse(mouseName="LightgunMouse",controllerName="WiimoteButtons", horizontal=False,rumble=False):
    global running
    
    size = WINDOW_SIZE or (1920,int(0.5+1920/CONFIG.aspect))

    def updateLEDs():
        if horizontal:
            wm.led = wiimote.LED2_ON | wiimote.LED3_ON
        else:
            wm.led = wiimote.LED1_ON | wiimote.LED4_ON

    rumbleStarted = None

    with myinput.AbsMouseInput(size, name=mouseName) as device:
        with myinput.KeyInput(name=controllerName) as device2:
            try:
                prevButtons = 0
                prevNunchukX = 128
                prevNunchukY = 128
                uinputPressed = set()
                CONNECTED_EVENT.wait()
                if crash:
                    sys.exit(1)
                updateLEDs()
                
                def press(dev, u):
                    if u not in uinputPressed:
                        dev.press(u)
                        uinputPressed.add(u)
                        
                def release(dev, u):
                    if u in uinputPressed:
                        dev.release(u)
                        uinputPressed.remove(u)
                
                while running:
                    wiimoteWait()
                    buttons = getButtons(wm.state)
                    updateAcceleration(wm.state)
                    pressed = buttons &~ prevButtons
                    released = ~buttons & prevButtons
                    prevButtons = buttons
                    
                    if buttons & wiimote.BTN_MINUS:
                        if pressed & wiimote.BTN_PLUS:
                            horizontal = not horizontal
                            updateLEDs()
                        map = minusVerticalMap if not horizontal else minusHorizontalMap
                        for wii,u in map:
                            if pressed & wii:
                                press(device2, u)
                            elif released & wii:
                                release(device2, u)
                    elif pressed or released:
                        map = verticalMap if not horizontal else horizontalMap

                        for wii,u in map:
                            dev = device if (u == myinput.BTN_LEFT or u == myinput.BTN_RIGHT) else device2
                            if pressed & wii:
                                press(dev, u)
                                if rumble:
                                    wm.rumble = True
                                    rumbleStarted = time.monotonic()
                            elif released & wii:
                                release(dev, u)

                    if rumble and rumbleStarted and rumbleStarted + RUMBLE_TIME <= time.monotonic():
                        wm.rumble = False
                                
                    if 'nunchuk' in wm.state:
                        def stick(offset,prevOffset,key):
                            if offset < NUNCHUK_DEADZONE-NUNCHUK_HYSTERESIS and prevOffset >= NUNCHUK_DEADZONE-NUNCHUK_HYSTERESIS:
                                release(device2, key)
                            elif offset >= NUNCHUK_DEADZONE:
                                press(device2, key)

                        x,y = wm.state['nunchuk']['stick']

                        stick(x-128,prevNunchukX-128,myinput.KEY_RIGHT)
                        stick(128-x,128-prevNunchukX,myinput.KEY_LEFT)
                        stick(y-128,prevNunchukY-128,myinput.KEY_UP)
                        stick(128-y,128-prevNunchukY,myinput.KEY_DOWN)

                        prevNunchukX, prevNunchukY = x,y

                    if not horizontal:
                        ir = wm.state.get("ir",[None,None,None,None])
                        irQuad = getIRQuad(ir)
                        if irQuad:
                            xy = CONFIG.pointerPosition(irQuad)
                            if xy is not None:
                                x,y = xy
                                x1 = int(size[0]*x)
                                y1 = int(size[1]*(1-y))
                                device.moveTo(x1,y1)
                            
            except KeyboardInterrupt:
                pass
            finally:
                for u in uinputPressed:
                    (device if u == myinput.BTN_LEFT or u == myinput.BTN_RIGHT else device2).release(u)
                    
def connectMessage(msg):
    if args.background_connect:
        return
    if not MYFONT:
        print(msg)
    else:
        surface.fill(BLACK)
        drawText(msg)
        drawText("Make sure Wii is turned off", y=0.7)
        drawText("Press ESC to exit", y=0.8)
        pygame.display.flip()

def connect(backgroundTimeout=0,silent=False):
    global wm, lastMessage, CENTER_X, CENTER_Y, crash, calibrationHomography
    wm = None
    t0 = time.monotonic()
    CONNECTED_EVENT.clear()
    crash = False
    while True:
        try:
            print("Attempting to connect to Wii Remote")
            wm = wiimote.Wiimote(connectCallback=connectMessage if not silent else None)
            print("ID:",wm.id)
            if USE_CALIBRATION_HOMOGRAPHY and hasattr(wm,'irCalibration'):
                calibrationHomography = Homography(wm.irCalibration,DEFAULT_IR_CALIBRATION)
                CENTER_X = 512
                CENTER_Y = 384
                inv = Homography(DEFAULT_IR_CALIBRATION,wm.irCalibration)
                print("using calibration homography, center at ",inv.apply((512,384)))
            else:
                calibrationHomography = Homography(None,None)
                CENTER_X,CENTER_Y = CONFIG.getCenter(wm)
            wm.mesg_callback = wiimoteCallback
            wm.rpt_mode = wiimote.RPT_IR | wiimote.RPT_BTN | wiimote.RPT_ACC | wiimote.RPT_EXT
            wm.enable(wiimote.FLAG_MESG_IFC)
            wm.led = wiimote.LED1_ON | wiimote.LED4_ON
            # give it a bit of extra time for messages to start flowing
            CONNECTED_EVENT.set()
            lastMessage = time.monotonic()+5
            return
        except (RuntimeError,OSError):
            if (backgroundTimeout and time.monotonic() > t0 + backgroundTimeout) or abortConnect:
                print("Giving up, connecting a fake wiimote")
                wm = FakeWiimote()
                CONNECTED_EVENT.set()
                return
        except Exception as e:
            print("Error in thread: ",e)
            crash = True
            CONNECTED_EVENT.set()
            print("Exiting thread")
            return

def run(command):
    global running, args, abortConnect
    print("lightgun: run "+command)
    subprocess.run(command, shell=True)
    print("lightgun: finished running")
    running = False
    abortConnect = True
                
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Calibrate and use Wiimote with two/four IR LEDs around screen.")
    parser.add_argument("--two-point", action="store_true", help="Force two LED mode [experimental]")
    parser.add_argument("-c", "--calibrate", action="store_true", help="Force calibration")
    parser.add_argument("-C", "--center", action="store_true", help="Center calibration for individual Wiimote")
    parser.add_argument("-M", "--measure", action="store_true", help="Calibrate by manual measurement of IR LED positions.")
    parser.add_argument("-w", "--width", type=float, default=1, help="Screen width for measurement calibration in preferred units.")
    parser.add_argument("-d", "--demo", action="store_true", help="Demo")
    parser.add_argument("-f", "--flexible-led-placement", action="store_true", help="Do not assume the top and bottom LED pairs are horizontal")
    parser.add_argument("-o", "--horizontal", action="store_true", help="Horizontal mode (without lightgun)")
    parser.add_argument("-t", "--terminal", action="store_true", help="Use terminal rather than pygame (doesn't work for calibration)")
    parser.add_argument("-m", "--mouse-name", help="Set name of mouse device", default="LightgunMouse")
    parser.add_argument("-b", "--buttons-name", help="Set name of buttons device", default="WiimoteButtons")
    parser.add_argument("-l", "--led-file", help="Configuration file for LEDs", default=LED_FILE)
    parser.add_argument("-B", "--background-connect", type=float, default=0, help="Connect in background for this many seconds")
    parser.add_argument("-r", "--rumble", action="store_true", help="Rumble on fire")
    parser.add_argument("-s", "--sensitivity", type=int, default=-1, help="IR sensitivity (1-5)")
    parser.add_argument("--p3p", action="store_true", help="Allow P3P as fallback")
    parser.add_argument("--p2pa", action="store_true", help="Allow P2PA as fallback")
    parser.add_argument("command", help="Run this command while simulating a mouse", nargs="?")
    args = parser.parse_args()

    try:
        os.mkdir(CONFIG_DIR)
    except:
        pass

    USE_P3P = args.p3p
    USE_P2PA = args.p2pa
    NUM_POINTS = 2 if args.two_point else 4
    
    LED_FILE = args.led_file
    CONFIG = Config()

    if args.sensitivity >= 0:
        wiimote.set_ir_sensitivity(args.sensitivity)
        
    if args.calibrate and args.two_point:
        print("Calibration is not compatible with two-point mode.")
        sys.exit(1)
    
    if args.calibrate or args.measure:
        ledLocations = None
    else:
        ledLocations = CONFIG.ledLocations

    if not args.terminal and (not args.background_connect or not ledLocations or args.center):
        pygame.init()
        atexit.register(pygame.quit)
        WINDOW_SIZE = getDisplaySize()
        CONFIG.aspect = float(WINDOW_SIZE[0])/WINDOW_SIZE[1]
        MYFONT = pygame.font.SysFont(pygame.font.get_default_font(),int(FONT_SIZE*WINDOW_SIZE[1]))                
        surface = pygame.display.set_mode(WINDOW_SIZE, pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
        
    thread = threading.Thread(target=connect, args=(args.background_connect,))
    thread.daemon = True
    thread.start()

    if not args.terminal and (not args.background_connect or not ledLocations or args.center):
        running = True
        if not args.background_connect:
            while running and wm is None:
                checkQuitAndKeys()
                CONNECTED_EVENT.wait(0.5)
                if crash:
                    sys.exit(1)
            if not running:
                sys.exit(0)
    elif not args.background_connect:
        CONNECTED_EVENT.wait()
        if crash:
            sys.exit(1)
        print("Ready.")
        
    def cal():
        CONNECTED_EVENT.wait()
        if crash:
            sys.exit(1)
        if args.center:
            try:
                del calibrationFileData[wm.id]
            except KeyError:
                pass
        if not args.calibrate:
            return measure(flexible=args.flexible_led_placement,screenWidth=args.width)
        else:
            return calibrate(flexible=args.flexible_led_placement)

    if args.calibrate or args.measure:
        if cal():
            demo()
    elif args.center:
        center()
    else:
        if ledLocations is None:
            if not cal():
                print("Missing calibration map")
                sys.exit(1)
        running = True
        if args.demo:
            demo()
        else:
            if not args.terminal:
                pygame.quit()
                atexit.unregister(pygame.quit)
            if args.command:
                thread = threading.Thread(target=run, args=(args.command,))
                thread.daemon = True
                thread.start()
            emulateMouse(mouseName=args.mouse_name,controllerName=args.buttons_name,horizontal=args.horizontal,rumble=args.rumble)
