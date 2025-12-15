"""封装音量获取方法，屏蔽 COM 生命周期细节。"""
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
    """启动独立 COM 线程读取主音量，避免 UI 线程卡死。"""

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
        self._ready.wait()  # 等待后台线程完成初始化，保证后续调用可用
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
    @staticmethod
    def _resolve_activate(devices):
        """兼容不同 pycaw 版本，返回可用的 Activate 调用。"""

        candidates = [devices]
        for attr in ("_device", "device", "_ctl", "interface", "_AudioDevice__device", "_AudioDevice__ctl"):
            raw = getattr(devices, attr, None)
            if raw is not None:
                candidates.append(raw)
        try:
            candidates.extend(devices.__dict__.values())
        except Exception:
            pass

        for obj in candidates:
            activate = getattr(obj, "Activate", None)
            if callable(activate):
                return activate
        return None

    # ------------------------------------------------------------------
    @staticmethod
    def _waveout_volume():
        """使用 winmm 作为兜底方案，避免 pycaw 版本差异导致失败。"""

        try:
            from ctypes import byref, c_uint, windll
        except Exception:
            return None

        class _WaveOutEndpoint:
            def GetMasterVolumeLevelScalar(self) -> float:
                value = c_uint()
                result = windll.winmm.waveOutGetVolume(0, byref(value))
                if result != 0:
                    raise OSError(f"waveOutGetVolume failed with code {result}")
                raw = value.value
                left = raw & 0xFFFF
                right = (raw >> 16) & 0xFFFF
                return float(left + right) / float(0xFFFF * 2)

            def Release(self) -> None:
                return None

        return _WaveOutEndpoint()

    # ------------------------------------------------------------------
    def _run(self) -> None:
        coinited = False
        self._startup_error: Exception | None = None
        volume = None
        try:
            if pythoncom is not None:
                pythoncom.CoInitialize()  # 每个线程单独初始化 COM
                coinited = True
            devices = AudioUtilities.GetSpeakers()
            activate = self._resolve_activate(devices)
            if activate is None:
                volume = self._waveout_volume()
                if volume is None:
                    raise AttributeError(
                        f"AudioDevice has no Activate; available attrs: {sorted(set(dir(devices)))}"
                    )
            else:
                interface = activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))  # 获取音量接口指针
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
        """返回当前主音量 (0.0 - 1.0)。"""

        future: Future = Future()
        # 将查询任务投递到 COM 线程，确保线程安全
        self._tasks.put((lambda volume: float(volume.GetMasterVolumeLevelScalar()), future))
        return future.result()
