Instructions:
https://www.instructables.com/Accurate-Wiimote-Light-Gun-on-Raspberry-PI/

On Windows, you need the hidapi library.

On Linux, it should work with pydbus (need to install) and sockets, or you can edit wiimote.py to
always use hidapi. In the latter case, you need to pre-pair your Wiimote before starting lightgun.py