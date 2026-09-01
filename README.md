You can use this with either the cwiid or wiiuse library and their python wrappings.
cwiid is only for Linux.

If you have both installed, edit wiimote.py to set WIIUSE = True or WIIUSE = False,
depending on whether you want to use wiiuse.

CWIID notes:
    On Raspberry PI, you may want to use this fork: https://github.com/arpruss/cwiid-1

WIIUSE notes:
    Install my python fork of the wiiuse wrapper: https://github.com/arpruss/pywiiuse
    You also need to install the .so or .dll library. There are some notes with my
    wrapper.
    
With Windows Wiiuse, you can only calibrate a single wiimote.

Calibration instructions are here: https://www.instructables.com/Accurate-Wiimote-Light-Gun-on-Raspberry-PI/

