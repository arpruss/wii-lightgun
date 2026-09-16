# AI slop but seems to work
#

import time
from pydbus import SystemBus

def scan_dbus_poll(timeout=10,blacklist=set(),connectAndPair=False,nameMatch=("RVL-CNT","RVT-CNT")):
    bus = SystemBus()
    adapter = bus.get('org.bluez', '/org/bluez/hci0')
    manager = bus.get('org.bluez', '/')

    try:
        adapter.StartDiscovery()
    except Exception:
        pass  # Discovery might already be active

    start_time = time.monotonic()
    found_mac = None
    found_name = None

    try:
        while time.monotonic() - start_time < timeout:
            # Check all active devices known to BlueZ
            objects = manager.GetManagedObjects()
            
            for path, interfaces in objects.items():
                if 'org.bluez.Device1' in interfaces:
                    dev = interfaces['org.bluez.Device1']
                    name = dev.get('Name', '')
                    uname = name.upper()
                    match = False
                    for n in nameMatch:
                        if n.upper() in uname:
                            match = True
                            break
                    if match:
                        found_mac = dev.get('Address')
                        if not found_mac in blacklist:
                            found_name = name
                            print(f"--> Found device {found_name}. MAC: {found_mac}")
                            if connectAndPair:
                                try:
                                    device = bus.get('org.bluez', path)
                                    device.Trusted = True
                                    device.Connect()
                                except:
                                    found_mac = None
                                    continue
                            break
            
            if found_mac:
                break
                
            time.sleep(0.1)  # Low-latency polling step
            
    finally:
        try:
            adapter.StopDiscovery()
        except Exception:
            pass

    return found_mac,name

if __name__ == "__main__":
    mac = scan_dbus_poll(timeout=10)
    if not mac:
        print("Scan timed out.")
