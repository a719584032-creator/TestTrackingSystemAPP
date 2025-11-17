"""Shared volume endpoint access that hides COM lifecycle details."""
from __future__ import annotations

import atexit
import threading
from concurrent.futures import Future
from queue import Queue
from typing import Callable, Optional

from ctypes import POINTER, cast
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

VolumeCallable = Callable[[IAudioEndpointVolume], float]

try:  # pragma: no cover - Windows specific
    import pythoncom
except ImportError:  # pragma: no cover
    pythoncom = None


class VolumeEndpointService:
    """Runs a dedicated COM thread to read master volume safely."""

    _instance: Optional["VolumeEndpointService"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._tasks: "Queue[tuple[VolumeCallable, Future]]" = Queue()
        self._ready = threading.Event()
        self._shutdown = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="VolumeEndpointService",
        )
        self._thread.start()
        self._ready.wait()
        if self._startup_error:
            raise RuntimeError(f"初始化音量监视线程失败: {self._startup_error}") from self._startup_error
        atexit.register(self.shutdown)

    # ------------------------------------------------------------------
    @classmethod
    def instance(cls) -> "VolumeEndpointService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    # ------------------------------------------------------------------
    def _run(self) -> None:
        coinited = False
        self._startup_error: Exception | None = None
        volume = None
        try:
            if pythoncom is not None:
                pythoncom.CoInitialize()
                coinited = True
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as exc:  # pragma: no cover - hardware/COM init failures
            self._startup_error = exc
            self._ready.set()
            return
        else:
            self._ready.set()

        while True:
            task = self._tasks.get()
            if task is None:
                break
            func, future = task
            if future.set_running_or_notify_cancel():
                try:
                    result = func(volume)
                except Exception as exc:  # pragma: no cover - actual COM errors are rare
                    future.set_exception(exc)
                else:
                    future.set_result(result)

        if volume is not None:
            try:
                volume.Release()
            except Exception:
                pass
        if coinited and pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        if self._shutdown.is_set():
            return
        self._shutdown.set()
        self._tasks.put(None)
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

    # ------------------------------------------------------------------
    def get_volume(self) -> float:
        """Return the current master volume level (0.0 - 1.0)."""

        future: Future = Future()
        self._tasks.put((lambda volume: float(volume.GetMasterVolumeLevelScalar()), future))
        return future.result()
