# AI slop
import ctypes
from ctypes import wintypes


# ---------------------------------------------------------------------------
# Windows DLLs
# ---------------------------------------------------------------------------

# IMPORTANT:
# use_last_error=True makes ctypes capture the Windows thread-local
# GetLastError() value correctly after Win32 API calls.
setupapi = ctypes.WinDLL(
    "setupapi.dll",
    use_last_error=True,
)

cfgmgr32 = ctypes.WinDLL(
    "cfgmgr32.dll",
    use_last_error=True,
)

hid = ctypes.WinDLL(
    "hid.dll",
    use_last_error=True,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010

ERROR_SUCCESS = 0
ERROR_NO_MORE_ITEMS = 259
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_INVALID_DATA = 13

CR_SUCCESS = 0x00000000
CR_NO_SUCH_DEVNODE = 0x0000000D

CM_GETIDLIST_FILTER_NONE = 0x00000000


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.POINTER(ctypes.c_ulong)),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.POINTER(ctypes.c_ulong)),
    ]


# ---------------------------------------------------------------------------
# Function declarations
# ---------------------------------------------------------------------------

# HID -----------------------------------------------------------------------

hid.HidD_GetHidGuid.argtypes = [
    ctypes.POINTER(GUID),
]

hid.HidD_GetHidGuid.restype = None


# SetupAPI ------------------------------------------------------------------

setupapi.SetupDiGetClassDevsW.argtypes = [
    ctypes.POINTER(GUID),
    wintypes.LPCWSTR,
    wintypes.HWND,
    wintypes.DWORD,
]

setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE


setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(SP_DEVINFO_DATA),
    ctypes.POINTER(GUID),
    wintypes.DWORD,
    ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
]

setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL


setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(SP_DEVINFO_DATA),
]

setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL


setupapi.SetupDiDestroyDeviceInfoList.argtypes = [
    wintypes.HANDLE,
]

setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL


setupapi.SetupDiGetDeviceInstanceIdW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(SP_DEVINFO_DATA),
    wintypes.LPWSTR,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]

setupapi.SetupDiGetDeviceInstanceIdW.restype = wintypes.BOOL


# Configuration Manager -----------------------------------------------------

cfgmgr32.CM_Get_Parent.argtypes = [
    ctypes.POINTER(wintypes.DWORD),
    wintypes.DWORD,
    wintypes.DWORD,
]

cfgmgr32.CM_Get_Parent.restype = wintypes.DWORD


cfgmgr32.CM_Get_Device_IDW.argtypes = [
    wintypes.DWORD,
    wintypes.LPWSTR,
    wintypes.ULONG,
    wintypes.ULONG,
]

cfgmgr32.CM_Get_Device_IDW.restype = wintypes.DWORD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _winerror():
    """
    Return the current ctypes-captured Windows last-error value.
    """

    return ctypes.get_last_error()


def _get_device_instance_id(hdevinfo, devinfo):
    """
    Return the PnP instance ID for an SP_DEVINFO_DATA.

    Returns None if the ID cannot be obtained.
    """

    size = 256

    while True:
        buffer = ctypes.create_unicode_buffer(size)

        ctypes.set_last_error(ERROR_SUCCESS)

        ok = setupapi.SetupDiGetDeviceInstanceIdW(
            hdevinfo,
            ctypes.byref(devinfo),
            buffer,
            size,
            None,
        )

        if ok:
            return buffer.value

        error = _winerror()

        if error != ERROR_INSUFFICIENT_BUFFER:
            return None

        size *= 2

        if size > 32768:
            return None


def _get_interface_path(
    hdevinfo,
    interface_data,
    devinfo,
):
    """
    Get the Windows device interface path from
    SP_DEVICE_INTERFACE_DATA.

    Returns None on failure.
    """

    required_size = wintypes.DWORD()

    # -----------------------------------------------------------------------
    # First call:
    #
    # Ask Windows how large the output buffer needs to be.
    #
    # This call is EXPECTED to fail with ERROR_INSUFFICIENT_BUFFER.
    # -----------------------------------------------------------------------

    ctypes.set_last_error(ERROR_SUCCESS)

    ok = setupapi.SetupDiGetDeviceInterfaceDetailW(
        hdevinfo,
        ctypes.byref(interface_data),
        None,
        0,
        ctypes.byref(required_size),
        ctypes.byref(devinfo),
    )

    if not ok:
        error = _winerror()

        if error != ERROR_INSUFFICIENT_BUFFER:
            return None

    if required_size.value == 0:
        return None

    # -----------------------------------------------------------------------
    # SP_DEVICE_INTERFACE_DETAIL_DATA_W:
    #
    # DWORD cbSize;
    # WCHAR DevicePath[1];
    #
    # The structure has architecture-dependent alignment.
    # -----------------------------------------------------------------------

    if ctypes.sizeof(ctypes.c_void_p) == 8:
        cb_size = 8
    else:
        cb_size = 6

    buffer = ctypes.create_string_buffer(
        required_size.value
    )

    # Write cbSize.
    ctypes.cast(
        buffer,
        ctypes.POINTER(wintypes.DWORD),
    )[0] = cb_size

    # -----------------------------------------------------------------------
    # Second call:
    #
    # Actually retrieve the device path.
    # -----------------------------------------------------------------------

    ctypes.set_last_error(ERROR_SUCCESS)

    ok = setupapi.SetupDiGetDeviceInterfaceDetailW(
        hdevinfo,
        ctypes.byref(interface_data),
        buffer,
        required_size.value,
        ctypes.byref(required_size),
        ctypes.byref(devinfo),
    )

    if not ok:
        return None

    # DevicePath starts immediately after cbSize.
    offset = cb_size

    return ctypes.wstring_at(
        ctypes.addressof(buffer) + offset
    )


# ---------------------------------------------------------------------------
# HID device lookup
# ---------------------------------------------------------------------------

def _find_hid_devinst(hid_path):
    if isinstance(hid_path, bytes):
        hid_path = hid_path.decode("utf-8", errors="replace")

    target = hid_path.lower()

    hid_guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(hid_guid))

    hdevinfo = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(hid_guid),
        None,
        None,
        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE,
    )

    if hdevinfo == wintypes.HANDLE(-1).value:
        error = ctypes.get_last_error()
        raise ctypes.WinError(error)

    try:
        index = 0

        while True:
            interface_data = SP_DEVICE_INTERFACE_DATA()
            interface_data.cbSize = ctypes.sizeof(interface_data)

            if not setupapi.SetupDiEnumDeviceInterfaces(
                hdevinfo,
                None,
                ctypes.byref(hid_guid),
                index,
                ctypes.byref(interface_data),
            ):
                error = ctypes.get_last_error()

                if error in (ERROR_NO_MORE_ITEMS, 0):
                    break

                raise ctypes.WinError(error)

            # First call obtains required buffer size.
            required_size = wintypes.DWORD(0)

            setupapi.SetupDiGetDeviceInterfaceDetailW(
                hdevinfo,
                ctypes.byref(interface_data),
                None,
                0,
                ctypes.byref(required_size),
                None,
            )

            error = ctypes.get_last_error()

            if required_size.value == 0:
                index += 1
                continue

            # Allocate the exact required byte buffer.
            detail_buffer = ctypes.create_string_buffer(
                required_size.value
            )

            # SP_DEVICE_INTERFACE_DETAIL_DATA_W.cbSize
            #
            # Windows requires:
            #   8 bytes on 64-bit
            #   6 bytes on 32-bit
            cb_size = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6

            ctypes.memmove(
                detail_buffer,
                ctypes.byref(ctypes.c_uint32(cb_size)),
                ctypes.sizeof(ctypes.c_uint32),
            )

            devinfo = SP_DEVINFO_DATA()
            devinfo.cbSize = ctypes.sizeof(devinfo)

            if not setupapi.SetupDiGetDeviceInterfaceDetailW(
                hdevinfo,
                ctypes.byref(interface_data),
                detail_buffer,
                required_size.value,
                ctypes.byref(required_size),
                ctypes.byref(devinfo),
            ):
                error = ctypes.get_last_error()
                index += 1
                continue

            # The device path is a WCHAR string immediately after
            # the cbSize field.
            path_offset = ctypes.sizeof(wintypes.DWORD)

            interface_path = ctypes.wstring_at(
                ctypes.addressof(detail_buffer) + path_offset
            )

            interface_path_lower = interface_path.lower()

            if interface_path_lower == target:
                return devinfo.DevInst

            index += 1

    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdevinfo)

    return None

# ---------------------------------------------------------------------------
# Configuration Manager helpers
# ---------------------------------------------------------------------------

def _get_device_id(devinst):
    """
    Get a PnP device instance ID from a DEVINST.

    Returns:
        Device instance ID string
        or None on failure.
    """

    size = 512

    while True:

        buffer = ctypes.create_unicode_buffer(
            size
        )

        result = cfgmgr32.CM_Get_Device_IDW(
            devinst,
            buffer,
            size,
            0,
        )

        if result == CR_SUCCESS:
            return buffer.value

        size *= 2

        if size > 32768:
            return None


import re


def _format_bt_address(mac_hex):
    """Convert 12 hex digits to AA:BB:CC:DD:EE:FF."""
    mac_hex = mac_hex.upper()

    if len(mac_hex) != 12:
        return None

    if not all(c in "0123456789ABCDEF" for c in mac_hex):
        return None

    return ":".join(
        mac_hex[i:i + 2]
        for i in range(0, 12, 2)
    )


def _extract_mac_from_bthenum(instance_id):
    """
    Extract a Bluetooth MAC address from a BTHENUM instance ID.

    Supports:

        Older:
        BTHENUM\\DEV_001122334455\\...

        Newer:
        BTHENUM\\{SERVICE-GUID}_VID&xxxx_PID&xxxx\\
        ...&001122334455_C00000000

    Also accepts less strict variants where the 12-digit address
    is followed by an underscore or path separator.
    """

    if not instance_id:
        return None

    upper = instance_id.upper()

    if not upper.startswith("BTHENUM\\"):
        return None

    # ---------------------------------------------------------------
    # Format used by older Windows Bluetooth stacks:
    #
    # BTHENUM\DEV_001122334455\...
    # ---------------------------------------------------------------
    match = re.search(
        r"BTHENUM\\DEV_([0-9A-F]{12})(?:\\|$)",
        upper,
    )

    if match:
        return _format_bt_address(match.group(1))

    # ---------------------------------------------------------------
    # Newer Windows format:
    #
    # BTHENUM\{00001124-...}_VID&0002057E_PID&0306\
    # 7&399C2D54&0&0027091769B6_C00000000
    #
    # The final 12 hexadecimal characters before "_C..." are the
    # Bluetooth address.
    # ---------------------------------------------------------------
    match = re.search(
        r"&([0-9A-F]{12})_C[0-9A-F]+$",
        upper,
    )

    if match:
        return _format_bt_address(match.group(1))

    # ---------------------------------------------------------------
    # Slightly more permissive variant:
    #
    # ...&001122334455_...
    #
    # This covers stacks whose suffix isn't exactly "_CXXXXXXXXX".
    # ---------------------------------------------------------------
    match = re.search(
        r"&([0-9A-F]{12})_[^\\]+$",
        upper,
    )

    if match:
        return _format_bt_address(match.group(1))

    return None


def get_mac_from_hid_path(path):
    """
    Convert a Windows HID device interface path into the Bluetooth
    MAC address of its parent Bluetooth device.

    Returns:
        'AA:BB:CC:DD:EE:FF'
        or None if no Bluetooth parent can be found.
    """

    if isinstance(path, bytes):
        path = path.decode("utf-8", errors="replace")

    devinst = _find_hid_devinst(path)

    if devinst is None:
        return None

    current = devinst

    for _ in range(32):
        instance_id = _get_device_id(current)

        if instance_id:
            mac = _extract_mac_from_bthenum(instance_id)

            if mac:
                return mac

        parent = wintypes.DWORD()

        result = cfgmgr32.CM_Get_Parent(
            ctypes.byref(parent),
            current,
            0,
        )

        if result != CR_SUCCESS:
            break

        current = parent.value

    return None