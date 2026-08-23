#!/usr/bin/python3
import subprocess
import math
import sys
import uinput
import re
import atexit
import os
import socket
import time
import struct

udpMode = False
cmd = ["adb", "logcat", "godot:I", "*:S", "-e", "LightGun:Data"]
prox_close = "adb shell am broadcast -a com.oculus.vrpowermanager.prox_close"
prox_open = "adb shell am broadcast -a com.oculus.vrpowermanager.prox_open"
udp_listen_port = 45128
udp_send_port = 45129
sock = None
heartbeatTime = 5
lastHeartbeat = -heartbeatTime-1

header = "LightGun:Data "

map = ((1, uinput.BTN_MOUSE),
        (2, uinput.BTN_RIGHT),
        (4, uinput.KEY_Z),
        (8, uinput.KEY_X),
        (32, uinput.KEY_S))

def isMouse(u):
    return u == uinput.BTN_MOUSE or u == uinput.BTN_RIGHT

def emulateMouse(reader,mouseName="LightgunMouse",controllerName="WiimoteButtons",map=map):
    global running
    
    size = (1920,1080)
    events = [
        uinput.ABS_X + (0,size[0],0,0),
        uinput.ABS_Y + (0,size[1],0,0),
        uinput.BTN_LEFT,
        uinput.BTN_RIGHT
        ]
        
    events2 = [(uinput.KEY_ESC[0],i) for i in range(uinput.KEY_ESC[1], uinput.KEY_MICMUTE[1]+1)]

    with uinput.Device(events,name=mouseName) as device:
        with uinput.Device(events2,name=controllerName) as device2:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
            prevButtons = 0
            uinputPressed = set()
            prevX1 = -1
            prevY1 = -1

            for line in iter(reader,''): 
                line = line.strip()
                if not line:
                    continue
                try:
                    start = line.index(header)
                    data = line[start+len(header):].split(" ")
                    x = float(data[2])
                    y = float(data[3])
                    buttons = int(data[4])
                except ValueError:
                    continue

                def press(dev, u):
                    if u not in uinputPressed:
                        dev.emit(u, 1)
                        uinputPressed.add(u)
                        
                def release(dev, u):
                    if u in uinputPressed:
                        dev.emit(u, 0)
                        uinputPressed.remove(u)
                
                pressed = buttons &~ prevButtons
                released = ~buttons & prevButtons
                prevButtons = buttons
                    
                for cb,u in map:
                    if isMouse(u):
                        dev = device
                    else:
                        dev = device2
                    if pressed & cb:
                        press(dev, u)
                    elif released & cb:
                        release(dev, u)

                    if x < -5000 or y < -5000:
                        x1 = 0
                        y1 = 0
                    else:
                        x1 = int(x * size[0]+.5)
                        y1 = int((1-y) * size[1]+.5)
                        if x1 < 0:
                            x1 = 0
                        elif x1 >= size[0]:
                            x1 = size[0]-1
                        if y1 < 0:
                            y1 = 0
                        elif y1 >= size[1]:
                            y1 = size[1]

                    if x1 != prevX1 or y1 != prevY1:
                        prevX1 = x1
                        prevY1 = y1
                        print(x1,y1)
                        device.emit(uinput.ABS_X,x1,syn=False)
                        device.emit(uinput.ABS_Y,y1)

def udpInit():
    global sock
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', udp_listen_port))
    group = socket.inet_aton('224.0.0.1')
    mreq = struct.pack('4sL', group, socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

def udpDetect(seconds):
    t = time.time()
    sock.settimeout(seconds)
    while time.time() <= t + seconds:
        try:
            data, address = sock.recvfrom(80)
        except:
            return False
        message = data.decode('utf-8')
        if message.startswith(header):
            return True
    return False


def udpRead():
    while True:
        data, address = sock.recvfrom(80)
        message = data.decode('utf-8')
        if message.startswith(header):
            if time.time() >= lastHeartbeat + heartbeatTime:
                parts = message.split(' ')
                try:
                    out = "LightGun:Request "+socket.gethostbyname(socket.gethostname())
                    sock.sendto(bytes(out, "utf-8"), (parts[1], udp_send_port))
                    lastHeartbeat = time.time()
                except:
                    pass
            return message

if __name__ == '__main__':
    if sys.argv[1] == 'udp':
        udpInit()
        reader = udpRead
    elif sys.argv[1] == 'udpdetect':
        udpInit()
        if udpDetect(3):
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        atexit.register(os.system, prox_open)
        os.system(prox_close)
        subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        reader = process.stdout.readline
    emulateMouse(reader)
