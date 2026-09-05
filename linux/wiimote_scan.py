#
# AI slop but seems to work
#

import time
from pydbus import SystemBus

def scan_wiimote_dbus_poll(timeout=10,blacklist=set()):
    bus = SystemBus()
    adapter = bus.get('org.bluez', '/org/bluez/hci0')
    manager = bus.get('org.bluez', '/')

    try:
        adapter.StartDiscovery()
    except Exception:
        pass  # Discovery might already be active

    start_time = time.monotonic()
    found_mac = None

    try:
        while time.monotonic() - start_time < timeout:
            # Check all active devices known to BlueZ
            objects = manager.GetManagedObjects()
            
            for path, interfaces in objects.items():
                if 'org.bluez.Device1' in interfaces:
                    dev = interfaces['org.bluez.Device1']
                    name = dev.get('Name', '')
                    
                    if "Nintendo" in name or "RVL" in name:
                        found_mac = dev.get('Address')
                        if not found_mac in blacklist:
                            print(f"--> Found Wiimote! MAC: {found_mac}")
                            break
            
            if found_mac:
                break
                
            time.sleep(0.1)  # Low-latency polling step
            
    finally:
        try:
            adapter.StopDiscovery()
        except Exception:
            pass

    return found_mac

if __name__ == "__main__":
    mac = scan_wiimote_dbus_poll(timeout=10)
    if not mac:
        print("Scan timed out.")
