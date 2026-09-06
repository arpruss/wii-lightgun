import wiimote
import time
import myinput
import threading
import subprocess
import sys

FRACTION = 0.75

zeroValues = None
lastValues = None
calibrate = False

pressed = set()

zeroed = {"top_left":0, "top_right":0, "bottom_left":0, "bottom_right":0}

def press(key,state):
    if bool(state) != (key in pressed):
        if state:
            controller.press(key)
            pressed.add(key)
        else:
            controller.release(key)
            pressed.remove(key)

def update(data):
    values = {}
    for i in data.keys():
        values[i] = data[i]-zeroed[i]
    right = values['top_right']+values['bottom_right']
    #left = values['top_left']+values['bottom_left']
    top = values['top_left']+values['top_right']
    bottom = values['bottom_left']+values['bottom_right']
    total = top+bottom
    if total < 20:
        press(myinput.KEY_UP, 0)
        press(myinput.KEY_DOWN, 0)
        press(myinput.KEY_RIGHT, 0)
        press(myinput.KEY_LEFT, 0)
    else:
        if top > FRACTION * total:
            press(myinput.KEY_UP, 1)
            press(myinput.KEY_DOWN, 0)
        elif top < (1-FRACTION) * total:
            press(myinput.KEY_UP, 0)
            press(myinput.KEY_DOWN, 1)
        else:
            press(myinput.KEY_UP, 0)
            press(myinput.KEY_DOWN, 0)
        if right > FRACTION * total:
            press(myinput.KEY_RIGHT, 1)
            press(myinput.KEY_LEFT, 0)
        elif right < (1-FRACTION) * total:
            press(myinput.KEY_RIGHT, 0)
            press(myinput.KEY_LEFT, 1)
        else:
            press(myinput.KEY_RIGHT, 0)
            press(myinput.KEY_LEFT, 0)

def wiimoteCallback(event,t):
    global zeroed
    if "balance_board" in event:
        bb = event["balance_board"]
    else:
        bb = None
    if event["buttons"] & wiimote.BTN_A:
        press(myinput.KEY_SPACE, 1)
        if bb and "weight_calib" in bb:
            zeroed = bb["weight_calib"]
    else:
        press(myinput.KEY_SPACE, 0)
    if bb and "weight_calib" in bb:
        update(bb["weight_calib"])

def go(wm):
    global calibration,controller
    print("connected")

    with myinput.KeyInput(name="BalanceController") as c:
        controller = c

        wm.mesg_callback = wiimoteCallback

        while running:
            time.sleep(0.25)

def connect():
    print("connecting")
    while True and running:
        try:
            wm = wiimote.Wiimote(connectCallback=print)
            wm.rpt_mode = wiimote.RPT_BTN | wiimote.RPT_EXT
            wm.enable()
            break        
        except RuntimeError:
            time.sleep(0.5)
    if running:
        go(wm)

def run(command):
    global running, args, abortConnect
    subprocess.run(command, shell=True)
    running = False

thread2 = threading.Thread(target=run, args=(sys.argv[1],))
thread2.daemon = True
thread2.start()

running = True

connect()
