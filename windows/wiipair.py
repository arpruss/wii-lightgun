#
# AI slop, but it seems to work well
#
import ctypes
from ctypes import wintypes
import time

# Load Windows Bluetooth API
try:
    bth = ctypes.windll.LoadLibrary("BluetoothApis.dll")
except OSError:
    bth = ctypes.windll.LoadLibrary("bthprops.cpl")

kernel32 = ctypes.windll.kernel32

# --- Struct Definitions ---
class BTH_ADDR(ctypes.Structure):
    _fields_ = [("ulonglong", ctypes.c_ulonglong)]

class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", wintypes.WORD), ("wMonth", wintypes.WORD),
        ("wDayOfWeek", wintypes.WORD), ("wDay", wintypes.WORD),
        ("wHour", wintypes.WORD), ("wMinute", wintypes.WORD),
        ("wSecond", wintypes.WORD), ("wMilliseconds", wintypes.WORD)
    ]

class BLUETOOTH_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("Address", BTH_ADDR),
        ("ulDeviceClass", wintypes.ULONG),
        ("fConnected", wintypes.BOOL),
        ("fRemembered", wintypes.BOOL),
        ("fAuthenticated", wintypes.BOOL),
        ("stLastSeen", SYSTEMTIME),
        ("stLastUsed", SYSTEMTIME),
        ("szName", ctypes.c_wchar * 248)
    ]

class BLUETOOTH_DEVICE_SEARCH_PARAMS(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("fReturnAuthenticated", wintypes.BOOL),
        ("fReturnRemembered", wintypes.BOOL),
        ("fReturnUnknown", wintypes.BOOL),
        ("fReturnConnected", wintypes.BOOL),
        ("fIssueInquiry", wintypes.BOOL),
        ("cTimeoutMultiplier", ctypes.c_ubyte),
        ("hRadio", wintypes.HANDLE)
    ]

class BLUETOOTH_FIND_RADIO_PARAMS(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD)]

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8)
    ]

HID_SERVICE_GUID = GUID(
    0x00001124, 0x0000, 0x1000,
    (ctypes.c_ubyte * 8)(0x80, 0x00, 0x00, 0x80, 0x5F, 0x9B, 0x34, 0xFB)
)
BLUETOOTH_SERVICE_ENABLE = 0x00000001

# --- Function Prototypes ---
bth.BluetoothFindFirstRadio.argtypes = [
    ctypes.POINTER(BLUETOOTH_FIND_RADIO_PARAMS),
    ctypes.POINTER(wintypes.HANDLE)
]
bth.BluetoothFindFirstRadio.restype = wintypes.HANDLE

bth.BluetoothFindRadioClose.argtypes = [wintypes.HANDLE]
bth.BluetoothFindRadioClose.restype = wintypes.BOOL

bth.BluetoothFindFirstDevice.argtypes = [
    ctypes.POINTER(BLUETOOTH_DEVICE_SEARCH_PARAMS),
    ctypes.POINTER(BLUETOOTH_DEVICE_INFO)
]
bth.BluetoothFindFirstDevice.restype = wintypes.HANDLE

bth.BluetoothFindNextDevice.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(BLUETOOTH_DEVICE_INFO)
]
bth.BluetoothFindNextDevice.restype = wintypes.BOOL

bth.BluetoothFindDeviceClose.argtypes = [wintypes.HANDLE]
bth.BluetoothFindDeviceClose.restype = wintypes.BOOL

bth.BluetoothRemoveDevice.argtypes = [ctypes.POINTER(BTH_ADDR)]
bth.BluetoothRemoveDevice.restype = wintypes.DWORD

bth.BluetoothSetServiceState.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
    ctypes.POINTER(GUID),
    wintypes.DWORD
]
bth.BluetoothSetServiceState.restype = wintypes.DWORD


def get_local_radio_handle():
    radio_params = BLUETOOTH_FIND_RADIO_PARAMS()
    radio_params.dwSize = ctypes.sizeof(BLUETOOTH_FIND_RADIO_PARAMS)
    hRadio = wintypes.HANDLE()

    hFindRadio = bth.BluetoothFindFirstRadio(
        ctypes.byref(radio_params),
        ctypes.byref(hRadio)
    )
    if not hFindRadio:
        return None

    bth.BluetoothFindRadioClose(hFindRadio)
    return hRadio


def pair_wiimote(timeout=30):
    """
    Scans for and pairs a Wiimote in 1+2 discoverable mode.

    :param timeout: Maximum scan duration in seconds (default 30). Set to None for infinite.
    :return: True if successfully paired, False if timed out or failed.
    """
    hRadio = get_local_radio_handle()
    if not hRadio:
        print("Error: Could not access local Bluetooth adapter.")
        return False

    try:
        search_params = BLUETOOTH_DEVICE_SEARCH_PARAMS()
        search_params.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_SEARCH_PARAMS)
        search_params.fReturnUnknown = True
        search_params.fReturnRemembered = True
        search_params.fReturnAuthenticated = True
        search_params.fIssueInquiry = True
        search_params.cTimeoutMultiplier = 2  # ~2.56 sec inquiry cycle
        search_params.hRadio = hRadio

        start_time = time.time()
        timeout_str = f"{timeout}s" if timeout is not None else "infinite"
        print(f"Scanning for Wiimotes... (Press 1+2 now | Timeout: {timeout_str})")

        while True:
            # Check if overall timeout limit has been exceeded
            if timeout is not None and (time.time() - start_time) >= timeout:
                print(f"Scan timed out after {timeout} seconds without pairing a Wiimote.")
                return False

            device_info = BLUETOOTH_DEVICE_INFO()
            device_info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)

            hFind = bth.BluetoothFindFirstDevice(
                ctypes.byref(search_params),
                ctypes.byref(device_info)
            )

            target_device = None

            if hFind:
                more_devices = True
                while more_devices:
                    name = device_info.szName
                    if "Nintendo" in name or "RVL-CNT" in name:
                        target_device = device_info
                        break
                    more_devices = bth.BluetoothFindNextDevice(hFind, ctypes.byref(device_info))

                # Release discovery handle lock on the adapter
                bth.BluetoothFindDeviceClose(hFind)

            if target_device:
                print(f"Found Wiimote ({target_device.szName}). Cleaning stale records and pairing...")

                # Purge stale registry entries
                bth.BluetoothRemoveDevice(ctypes.byref(target_device.Address))
                time.sleep(0.2)

                # Direct HID service activation
                res = bth.BluetoothSetServiceState(
                    hRadio,
                    ctypes.byref(target_device),
                    ctypes.byref(HID_SERVICE_GUID),
                    BLUETOOTH_SERVICE_ENABLE
                )

                if res == 0:
                    print("Wiimote successfully paired and HID service activated!")
                    return True
                else:
                    print(f"BluetoothSetServiceState failed with code: {res}. Retrying...")

            time.sleep(0.5)

    finally:
        kernel32.CloseHandle(hRadio)


if __name__ == "__main__":
    # Scan for up to 15 seconds before giving up
    success = pair_wiimote(timeout=15)
    print(f"Pairing Result: {success}")