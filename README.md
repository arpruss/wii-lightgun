Instructions:
https://www.instructables.com/Accurate-Wiimote-Light-Gun-on-Raspberry-PI/

On Windows, you need either the wiiuse library (with python wrappings)
or the hidapi library.

On Linux, it should work with pydbus (need to install) and sockets. But you can also
use it with cwiid (this is the best tested approach) or wiiuse.

You can edit the top of the lightgun.py and wiimote.py scripts to select which
library to use this with.

WIIUSE notes:
    Install my python fork of the wiiuse wrapper: https://github.com/arpruss/pywiiuse
    You also need to install the .so or .dll library. There are some notes with my
    wrapper.

CWIID notes:
    See the cwiid-notes.txt file.
