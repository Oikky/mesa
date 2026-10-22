"""Saída de áudio por app (o mesmo que Configurações › Som › Volume e dispositivos por app).

Usa a interface interna IAudioPolicyConfigFactory do Windows, a mesma que o EarTrumpet usa.
Não é documentada, então tudo aqui falha em silêncio se o Windows mudar.
"""
import ctypes
from ctypes import HRESULT, POINTER, byref, c_uint, c_void_p, c_wchar_p, WINFUNCTYPE
import sys

combase = ctypes.windll.combase
combase.WindowsCreateString.argtypes = [c_wchar_p, c_uint, POINTER(c_void_p)]
combase.WindowsDeleteString.argtypes = [c_void_p]
combase.WindowsGetStringRawBuffer.argtypes = [c_void_p, POINTER(c_uint)]
combase.WindowsGetStringRawBuffer.restype = c_wchar_p
combase.RoGetActivationFactory.argtypes = [c_void_p, c_void_p, POINTER(c_void_p)]


class GUID(ctypes.Structure):
    _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16), ("d3", ctypes.c_uint16), ("d4", ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, s):
        import uuid
        u = uuid.UUID(s)
        return cls(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))


IID = ("{ab3d4648-e242-459f-b02f-541c70306324}" if sys.getwindowsversion().build >= 21390
       else "{2a59116d-6c4f-45e0-a74f-707e3fef9258}")
DEVICE_FMT = "\\\\?\\SWD#MMDEVAPI#{}#{{e6327cad-dcec-4949-ae8a-991e976a79d2}}"
E_RENDER = 0
ROLES = (0, 1)  # eConsole, eMultimedia


def _hstring(s):
    h = c_void_p()
    if s:
        combase.WindowsCreateString(s, len(s), byref(h))
    return h


class Routing:
    def __init__(self):
        self.ok = False
        try:
            name = _hstring("Windows.Media.Internal.AudioPolicyConfig")
            factory = c_void_p()
            hr = combase.RoGetActivationFactory(name, byref(GUID.parse(IID)), byref(factory))
            combase.WindowsDeleteString(name)
            if hr != 0:
                raise OSError(hr)
            self._ptr = factory
            vtbl = ctypes.cast(factory, POINTER(POINTER(c_void_p))).contents
            self._set = WINFUNCTYPE(HRESULT, c_void_p, c_uint, c_uint, c_uint, c_void_p)(vtbl[25])
            self._get = WINFUNCTYPE(HRESULT, c_void_p, c_uint, c_uint, c_uint, POINTER(c_void_p))(vtbl[26])
            self.ok = True
        except Exception as e:
            print("[routing] indisponível:", repr(e))

    def get(self, pid):
        """ID do dispositivo (formato MMDevice) escolhido pro processo, ou None = padrão do Windows."""
        if not self.ok:
            return None
        h = c_void_p()
        try:
            self._get(self._ptr, pid, E_RENDER, 1, byref(h))
        except OSError:
            return None
        if not h.value:
            return None
        s = combase.WindowsGetStringRawBuffer(h, None)
        combase.WindowsDeleteString(h)
        # "\\?\SWD#MMDEVAPI#{0.0.0.00000000}.{...}#{e6327...}" -> "{0.0.0.00000000}.{...}"
        parts = s.split("#")
        return parts[2] if len(parts) >= 3 else None

    def set(self, pid, device_id):
        """device_id None volta pro padrão do Windows."""
        if not self.ok:
            return
        h = _hstring(DEVICE_FMT.format(device_id) if device_id else None)
        try:
            for role in ROLES:
                self._set(self._ptr, pid, E_RENDER, role, h)
        finally:
            if h.value:
                combase.WindowsDeleteString(h)
