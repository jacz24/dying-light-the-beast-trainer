"""Process memory helper for Windows. No dependencies. Read-only unless Process(..., write=True).

Step 1 of the walkthrough: attach to a process, find its base address, read bytes.
Run `python mem.py [exe name]` for a self-check. It reads the 'MZ' header of the target.
"""
import ctypes
import ctypes.wintypes as w
import os
import struct
import sys

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

TH32CS_SNAPPROCESS, TH32CS_SNAPMODULE, TH32CS_SNAPMODULE32 = 0x2, 0x8, 0x10
PROCESS_VM_READ, PROCESS_QUERY_INFORMATION = 0x10, 0x400
PROCESS_VM_WRITE, PROCESS_VM_OPERATION = 0x20, 0x8


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", w.DWORD),
                ("cntThreads", w.DWORD), ("th32ParentProcessID", w.DWORD),
                ("pcPriClassBase", w.LONG), ("dwFlags", w.DWORD), ("szExeFile", w.WCHAR * 260)]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", w.DWORD), ("th32ModuleID", w.DWORD), ("th32ProcessID", w.DWORD),
                ("GlblcntUsage", w.DWORD), ("ProccntUsage", w.DWORD),
                ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", w.DWORD),
                ("hModule", w.HANDLE), ("szModule", w.WCHAR * 256), ("szExePath", w.WCHAR * 260)]


class MBI(ctypes.Structure):  # MEMORY_BASIC_INFORMATION
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("PartitionId", w.WORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]


# Explicit types: without them ctypes cuts 64-bit handles to 32 bits.
k32.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
k32.CreateToolhelp32Snapshot.restype = w.HANDLE
for fn in (k32.Process32FirstW, k32.Process32NextW, k32.Module32FirstW, k32.Module32NextW):
    fn.argtypes = [w.HANDLE, ctypes.c_void_p]
k32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k32.OpenProcess.restype = w.HANDLE
k32.CloseHandle.argtypes = [w.HANDLE]
k32.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
k32.VirtualQueryEx.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.ReadProcessMemory.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.argtypes = k32.ReadProcessMemory.argtypes


def _walk(flags, pid, entry_type, first, nxt):
    """Yield every entry of a Toolhelp snapshot."""
    snap = k32.CreateToolhelp32Snapshot(flags, pid)
    if snap in (None, w.HANDLE(-1).value):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        e = entry_type()
        e.dwSize = ctypes.sizeof(e)
        ok = first(snap, ctypes.byref(e))
        while ok:
            yield e
            ok = nxt(snap, ctypes.byref(e))
    finally:
        k32.CloseHandle(snap)


class Process:
    def __init__(self, exe_name, pid=None, write=False):
        self.name, self.writable = exe_name, write
        self.pid = pid or next((e.th32ProcessID for e in _walk(
            TH32CS_SNAPPROCESS, 0, PROCESSENTRY32W, k32.Process32FirstW, k32.Process32NextW)
            if e.szExeFile.lower() == exe_name.lower()), None)
        if self.pid is None:
            raise RuntimeError(f"{exe_name} is not running")
        access = PROCESS_VM_READ | PROCESS_QUERY_INFORMATION | (PROCESS_VM_WRITE | PROCESS_VM_OPERATION if write else 0)
        self.handle = k32.OpenProcess(access, False, self.pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.base = self.module(exe_name)

    def running(self):
        """False once the process has ended (its exit code is no longer STILL_ACTIVE, 259)."""
        code = w.DWORD()
        return bool(k32.GetExitCodeProcess(self.handle, ctypes.byref(code))) and code.value == 259

    def module(self, mod_name):
        """Return the base address of a loaded module (the exe itself is a module)."""
        for m in _walk(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, self.pid, MODULEENTRY32W,
                       k32.Module32FirstW, k32.Module32NextW):
            if m.szModule.lower() == mod_name.lower():
                return m.modBaseAddr
        raise RuntimeError(f"module {mod_name} not found")

    def regions(self):
        """Yield (base, size, protect, type, reservation) for each committed region that is not NOACCESS or GUARD.
        reservation: the AllocationBase, shared by all regions of one VirtualAlloc (e.g. one heap segment)."""
        mbi, addr = MBI(), 0
        while addr < 1 << 47 and k32.VirtualQueryEx(self.handle, addr, ctypes.byref(mbi), ctypes.sizeof(mbi)):
            base = mbi.BaseAddress or 0
            if mbi.State == 0x1000 and not mbi.Protect & 0x101:
                yield base, mbi.RegionSize, mbi.Protect, mbi.Type, mbi.AllocationBase or 0
            addr = base + mbi.RegionSize

    def region_size(self, addr):
        """Bytes from addr to the end of its committed region (one VirtualQueryEx call), or 0."""
        mbi = MBI()
        if not k32.VirtualQueryEx(self.handle, addr, ctypes.byref(mbi), ctypes.sizeof(mbi)) or mbi.State != 0x1000:
            return 0
        return (mbi.BaseAddress or 0) + mbi.RegionSize - addr

    def read(self, addr, size):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(self.handle, addr, buf, size, ctypes.byref(got)):
            raise OSError(f"read failed at {addr:#x}: {ctypes.WinError(ctypes.get_last_error())}")
        return buf.raw

    def read_into(self, addr, buf, size):
        """Read size bytes into a writable buffer (a numpy array): no new object per read. False when the read fails."""
        got = ctypes.c_size_t()
        return bool(k32.ReadProcessMemory(self.handle, addr, buf.ctypes.data, size, ctypes.byref(got)))

    def u32(self, addr): return struct.unpack("<I", self.read(addr, 4))[0]
    def u64(self, addr): return struct.unpack("<Q", self.read(addr, 8))[0]
    def f32(self, addr): return struct.unpack("<f", self.read(addr, 4))[0]
    def vec3(self, addr): return struct.unpack("<3f", self.read(addr, 12))

    def write(self, addr, data):
        """Write bytes into the target. Only with Process(..., write=True)."""
        assert self.writable, "opened read-only: pass write=True"
        done = ctypes.c_size_t()
        if not k32.WriteProcessMemory(self.handle, addr, data, len(data), ctypes.byref(done)) or done.value != len(data):
            raise OSError(f"write failed at {addr:#x}: {ctypes.WinError(ctypes.get_last_error())}")

    def write_f32(self, addr, value): self.write(addr, struct.pack("<f", value))


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.basename(sys.executable)
    p = Process(target)
    print(f"{p.name}: pid={p.pid} base={p.base:#x}")
    assert p.read(p.base, 2) == b"MZ", "PE header not found at the base address"
    print("OK: read the 'MZ' header at the base address")
