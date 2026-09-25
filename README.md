Instructions:
https://www.instructables.com/Accurate-Wiimote-Light-Gun-on-Raspberry-PI/

On Windows, you need the hidapi library.

On Linux, it should work with pydbus (need to install) and sockets, or you can edit wiimote.py to
always use hidapi. In the latter case, you need to pre-pair your Wiimote before starting lightgun.py

For the --custom-map=filename option, the file should contain a list of pairs, on separate lines, each
of the form:
 button=key 
The options for the button are given in BTN_DICT in wiimote_constants.py, and the options for the
key are in KEY_DICT in myinput.py.

For instance:
 z=space
 c=f1
 b=mouseleft
 a=mouseright
maps Wiimote B and A to mouse-left and mouse-right, and Nunchuk Z and C to space and F1.