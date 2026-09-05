import ctypes
from ctypes import wintypes
import multiprocessing
import time
import sys


# ============================================================
# Windows Bluetooth API
# ============================================================

try:
    bth = ctypes.windll.LoadLibrary("BluetoothApis.dll")
except OSError:
    bth = ctypes.windll.LoadLibrary("bthprops.cpl")

kernel32 = ctypes.windll.kernel32


# ============================================================
# Constants
# ============================================================

ERROR_SUCCESS = 0
ERROR_BUSY = 170
ERROR_NOT_FOUND = 1168

BLUETOOTH_SERVICE_ENABLE = 0x00000001


# ============================================================
# Structure definitions
# ============================================================

class BTH_ADDR(ctypes.Structure):
    _fields_ = [
        ("ullLong", ctypes.c_ulonglong)
    ]


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", wintypes.WORD),
        ("wMonth", wintypes.WORD),
        ("wDayOfWeek", wintypes.WORD),
        ("wDay", wintypes.WORD),
        ("wHour", wintypes.WORD),
        ("wMinute", wintypes.WORD),
        ("wSecond", wintypes.WORD),
        ("wMilliseconds", wintypes.WORD),
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
        ("szName", ctypes.c_wchar * 248),
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
        ("hRadio", wintypes.HANDLE),
    ]


class BLUETOOTH_FIND_RADIO_PARAMS(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD)
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


# HID service:
# 00001124-0000-1000-8000-00805F9B34FB

HID_SERVICE_GUID = GUID(
    0x00001124,
    0x0000,
    0x1000,
    (ctypes.c_ubyte * 8)(
        0x80, 0x00, 0x00, 0x80,
        0x5F, 0x9B, 0x34, 0xFB
    )
)


# ============================================================
# Function prototypes
# ============================================================

bth.BluetoothFindFirstRadio.argtypes = [
    ctypes.POINTER(BLUETOOTH_FIND_RADIO_PARAMS),
    ctypes.POINTER(wintypes.HANDLE),
]
bth.BluetoothFindFirstRadio.restype = wintypes.HANDLE


bth.BluetoothFindRadioClose.argtypes = [
    wintypes.HANDLE
]
bth.BluetoothFindRadioClose.restype = wintypes.BOOL


bth.BluetoothFindFirstDevice.argtypes = [
    ctypes.POINTER(BLUETOOTH_DEVICE_SEARCH_PARAMS),
    ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
]
bth.BluetoothFindFirstDevice.restype = wintypes.HANDLE


bth.BluetoothFindNextDevice.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
]
bth.BluetoothFindNextDevice.restype = wintypes.BOOL


bth.BluetoothFindDeviceClose.argtypes = [
    wintypes.HANDLE
]
bth.BluetoothFindDeviceClose.restype = wintypes.BOOL


bth.BluetoothRemoveDevice.argtypes = [
    ctypes.POINTER(BTH_ADDR)
]
bth.BluetoothRemoveDevice.restype = wintypes.DWORD


bth.BluetoothSetServiceState.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
    ctypes.POINTER(GUID),
    wintypes.DWORD,
]
bth.BluetoothSetServiceState.restype = wintypes.DWORD


# ============================================================
# Utility functions
# ============================================================

def format_address(address):
    """Return Bluetooth address as XX:XX:XX:XX:XX:XX."""

    value = int(address.ullLong)

    return ":".join(
        f"{(value >> shift) & 0xFF:02X}"
        for shift in (40, 32, 24, 16, 8, 0)
    )


def is_wiimote(device):
    """Return True if the device appears to be a Wii Remote."""

    name = device.szName or ""

    return (
        "Nintendo" in name
        or "RVL-CNT" in name
    )


def copy_device_info(source):
    """
    Make an independent copy of BLUETOOTH_DEVICE_INFO.

    BluetoothFindNextDevice() reuses the structure supplied
    to it, so retaining a pointer/reference to the original
    structure isn't desirable.
    """

    destination = BLUETOOTH_DEVICE_INFO()

    ctypes.memmove(
        ctypes.byref(destination),
        ctypes.byref(source),
        ctypes.sizeof(source),
    )

    return destination


# ============================================================
# Get Bluetooth radio
# ============================================================

def get_local_radio_handle():

    radio_params = BLUETOOTH_FIND_RADIO_PARAMS()
    radio_params.dwSize = ctypes.sizeof(
        BLUETOOTH_FIND_RADIO_PARAMS
    )

    hRadio = wintypes.HANDLE()

    hFindRadio = bth.BluetoothFindFirstRadio(
        ctypes.byref(radio_params),
        ctypes.byref(hRadio),
    )

    if not hFindRadio:
        return None

    bth.BluetoothFindRadioClose(hFindRadio)

    return hRadio


# ============================================================
# Enumerate Bluetooth devices
# ============================================================

def enumerate_devices(
    hRadio,
    remembered=False,
    unknown=False,
    authenticated=False,
    connected=False,
    inquiry=False,
    timeout_multiplier=2,
):
    """
    Enumerate Bluetooth devices.

    For stale-record cleanup, inquiry=False is important:
    Windows searches its existing device records without
    initiating a new Bluetooth inquiry.
    """

    search_params = BLUETOOTH_DEVICE_SEARCH_PARAMS()

    search_params.dwSize = ctypes.sizeof(
        BLUETOOTH_DEVICE_SEARCH_PARAMS
    )

    search_params.fReturnRemembered = remembered
    search_params.fReturnUnknown = unknown
    search_params.fReturnAuthenticated = authenticated
    search_params.fReturnConnected = connected

    search_params.fIssueInquiry = inquiry
    search_params.cTimeoutMultiplier = timeout_multiplier

    search_params.hRadio = hRadio

    device_info = BLUETOOTH_DEVICE_INFO()
    device_info.dwSize = ctypes.sizeof(
        BLUETOOTH_DEVICE_INFO
    )

    hFind = bth.BluetoothFindFirstDevice(
        ctypes.byref(search_params),
        ctypes.byref(device_info),
    )

    if not hFind:
        return []

    devices = []

    try:

        while True:

            devices.append(
                copy_device_info(device_info)
            )

            if not bth.BluetoothFindNextDevice(
                hFind,
                ctypes.byref(device_info),
            ):
                break

    finally:

        bth.BluetoothFindDeviceClose(hFind)

    return devices


# ============================================================
# BluetoothRemoveDevice worker
# ============================================================

def _remove_device_worker(
    address_value,
    result_queue,
):
    """
    Execute BluetoothRemoveDevice() in a separate process.

    This protects the main application from a native Bluetooth
    API call that gets stuck inside Windows.
    """

    try:

        address = BTH_ADDR(address_value)

        result = bth.BluetoothRemoveDevice(
            ctypes.byref(address)
        )

        result_queue.put(
            ("result", int(result))
        )

    except Exception as exc:

        result_queue.put(
            ("exception", repr(exc))
        )


def remove_device_with_timeout(
    address,
    timeout=45,
):
    """
    Remove a Bluetooth device in a separate process.

    Returns:
        Windows error code on success/completion.
        None if the worker timed out.
    """

    ctx = multiprocessing.get_context("spawn")

    result_queue = ctx.Queue()

    address_value = int(address.ullLong)

    process = ctx.Process(
        target=_remove_device_worker,
        args=(
            address_value,
            result_queue,
        ),
    )

    process.start()

    start = time.monotonic()

    while process.is_alive():

        elapsed = time.monotonic() - start

        if elapsed >= timeout:

            print()
            print(
                f"ERROR: BluetoothRemoveDevice() "
                f"exceeded {timeout} seconds."
            )

            print("Terminating removal worker...")

            process.terminate()
            process.join(2)

            if process.is_alive():
                process.kill()
                process.join()

            return None

        print(
            f"\rRemoving stale record... "
            f"{elapsed:5.1f}s",
            end="",
            flush=True,
        )

        time.sleep(0.25)

    process.join()

    print()

    if result_queue.empty():
        return None

    kind, value = result_queue.get()

    if kind == "result":
        return value

    print(
        f"Removal worker exception: {value}"
    )

    return None


# ============================================================
# Clean stale Wii Remote records
# ============================================================

def clean_stale_wiimotes(hRadio):
    """
    Remove remembered but unauthenticated Wii Remote records.

    An authenticated remembered Wii Remote is left alone.

    IMPORTANT:
    No Bluetooth inquiry is performed here. Therefore the Wii
    Remote does not need to be in 1+2 mode while the potentially
    slow BluetoothRemoveDevice() operation runs.
    """

    print()
    print("Checking for remembered Wii Remote records...")

    devices = enumerate_devices(
        hRadio,
        remembered=True,
        unknown=False,
        authenticated=True,
        connected=True,
        inquiry=False,
    )

    wiimotes = [
        device
        for device in devices
        if is_wiimote(device)
    ]

    if not wiimotes:

        print(
            "No remembered Wii Remote records found."
        )

        return True

    print(
        f"Found {len(wiimotes)} remembered "
        f"Wii Remote record(s)."
    )

    purge_required = False

    for device in wiimotes:

        remembered = bool(device.fRemembered)
        authenticated = bool(device.fAuthenticated)
        connected = bool(device.fConnected)

        print()
        print(
            f"  {device.szName!r}"
        )
        print(
            f"  Address: "
            f"{format_address(device.Address)}"
        )
        print(
            f"  remembered={remembered} "
            f"authenticated={authenticated} "
            f"connected={connected}"
        )

        if remembered and authenticated:

            print(
                "  Already paired/authenticated; "
                "skipping purge."
            )

        elif remembered:

            print(
                "  Remembered but NOT authenticated; "
                "stale record requires purge."
            )

            purge_required = True

    if not purge_required:

        print()
        print(
            "All remembered Wii Remotes are "
            "authenticated. No purge necessary."
        )

        return True

    # --------------------------------------------------------
    # Remove only remembered + unauthenticated records.
    # --------------------------------------------------------

    for device in wiimotes:

        if not device.fRemembered:
            continue

        if device.fAuthenticated:
            continue

        print()
        print(
            f"Removing stale record:"
        )
        print(
            f"  {device.szName}"
        )
        print(
            f"  {format_address(device.Address)}"
        )

        print(
            "Windows may take about 30 seconds "
            "to complete this operation."
        )

        result = remove_device_with_timeout(
            device.Address,
            timeout=45,
        )

        if result is None:

            print()
            print(
                "ERROR: BluetoothRemoveDevice() "
                "did not complete."
            )

            return False

        if result == ERROR_SUCCESS:

            print(
                "Stale record removed successfully."
            )

        elif result == ERROR_NOT_FOUND:

            print(
                "Record was already removed."
            )

        else:

            print(
                f"BluetoothRemoveDevice returned "
                f"error {result}."
            )

            return False

    print()
    print(
        "Waiting for Bluetooth stack to settle..."
    )

    time.sleep(1.0)

    return True


# ============================================================
# Find Wii Remote through inquiry
# ============================================================

def find_wiimote(
    hRadio,
    timeout=15,
):
    """
    Perform a Bluetooth inquiry and find a Wii Remote.

    This function is only called after stale-record cleanup
    has finished.
    """

    search_params = BLUETOOTH_DEVICE_SEARCH_PARAMS()

    search_params.dwSize = ctypes.sizeof(
        BLUETOOTH_DEVICE_SEARCH_PARAMS
    )

    search_params.fReturnUnknown = True
    search_params.fReturnRemembered = True
    search_params.fReturnAuthenticated = True
    search_params.fReturnConnected = True

    search_params.fIssueInquiry = True

    # Approximately 2.56 seconds.
    search_params.cTimeoutMultiplier = 2

    search_params.hRadio = hRadio

    print()
    print(
        "Press 1+2 on the Wii Remote now!"
    )
    print(
        f"Scanning for Wii Remotes "
        f"(timeout: {timeout}s)..."
    )

    start_time = time.monotonic()

    while True:

        elapsed = time.monotonic() - start_time

        if elapsed >= timeout:

            print()
            print(
                f"Scan timed out after "
                f"{timeout} seconds."
            )

            return None

        device_info = BLUETOOTH_DEVICE_INFO()
        device_info.dwSize = ctypes.sizeof(
            BLUETOOTH_DEVICE_INFO
        )

        hFind = bth.BluetoothFindFirstDevice(
            ctypes.byref(search_params),
            ctypes.byref(device_info),
        )

        if hFind:

            try:

                while True:

                    if is_wiimote(device_info):

                        target = copy_device_info(
                            device_info
                        )

                        print()
                        print(
                            f"Found Wii Remote "
                            f"({target.szName})"
                        )

                        print(
                            f"Address: "
                            f"{format_address(target.Address)}"
                        )

                        print(
                            f"remembered="
                            f"{bool(target.fRemembered)} "
                            f"authenticated="
                            f"{bool(target.fAuthenticated)} "
                            f"connected="
                            f"{bool(target.fConnected)}"
                        )

                        return target

                    if not bth.BluetoothFindNextDevice(
                        hFind,
                        ctypes.byref(device_info),
                    ):
                        break

            finally:

                bth.BluetoothFindDeviceClose(
                    hFind
                )

        time.sleep(0.1)


# ============================================================
# Activate HID service
# ============================================================

def activate_hid_service(
    hRadio,
    device,
):
    """
    Enable the HID service for the Wii Remote.
    """

    print()
    print(
        "Activating HID service..."
    )

    result = bth.BluetoothSetServiceState(
        hRadio,
        ctypes.byref(device),
        ctypes.byref(HID_SERVICE_GUID),
        BLUETOOTH_SERVICE_ENABLE,
    )

    print(
        f"BluetoothSetServiceState returned "
        f"{result}"
    )

    if result == ERROR_SUCCESS:

        print()
        print(
            "Wiimote successfully paired and "
            "HID service activated!"
        )

        return True

    if result == ERROR_BUSY:

        print()
        print(
            "ERROR_BUSY (170): Windows reports "
            "the Bluetooth device is busy."
        )

    else:

        print()
        print(
            f"BluetoothSetServiceState failed "
            f"with error {result}."
        )

    return False


# ============================================================
# Main pairing function
# ============================================================

def pair_wiimote(
    timeout=20,connectCallback=None
):
    """
    Pair a Wii Remote.

    Algorithm:

        1. Enumerate remembered devices WITHOUT inquiry.
        2. If a Wii Remote is remembered and authenticated,
           leave it alone.
        3. If a Wii Remote is remembered but unauthenticated,
           remove its stale record.
        4. Wait for the Bluetooth stack to settle.
        5. Ask user to press 1+2.
        6. Perform Bluetooth inquiry.
        7. Find the Wii Remote.
        8. Enable its HID service.
    """
    
    if connectCallback is None:
        connectCallback = lambda x : None

    multiprocessing.freeze_support()

    hRadio = get_local_radio_handle()

    if not hRadio:

        print(
            "ERROR: Could not access local "
            "Bluetooth adapter."
        )

        return False

    try:
        connectCallback("Cleaning stale records")

        # ----------------------------------------------------
        # Phase 1: stale-record cleanup
        # ----------------------------------------------------

        if not clean_stale_wiimotes(
            hRadio
        ):

            connectCallback("Cleaning stale records failed")
            time.sleep(0.5)

        # ----------------------------------------------------
        # Phase 2: fresh discovery
        # ----------------------------------------------------

        connectCallback("Press 1+2 on Wii Remote")
        device = find_wiimote(
            hRadio,
            timeout=timeout,
        )

        if device is None:
            return False

        # ----------------------------------------------------
        # Phase 3: HID activation
        # ----------------------------------------------------

        return activate_hid_service(
            hRadio,
            device,
        )

    finally:

        kernel32.CloseHandle(
            hRadio
        )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":

    success = pair_wiimote(
        timeout=15
    )

    print()

    if success:
        print(
            "Pairing Result: SUCCESS"
        )
        sys.exit(0)

    else:
        print(
            "Pairing Result: FAILED"
        )
        sys.exit(1)