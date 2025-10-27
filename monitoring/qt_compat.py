"""兼容 wx.CallAfter 调用的 PyQt 工具模块。"""
from PyQt5 import QtCore


class _WxCompat(QtCore.QObject):
    """为旧版 wx 代码提供 PyQt 的兼容层。"""

    _call_after_signal = QtCore.pyqtSignal(object, tuple, dict)

    def __init__(self) -> None:
        super().__init__()
        # 通过队列连接确保回调在主线程执行。
        self._call_after_signal.connect(self._invoke, QtCore.Qt.QueuedConnection)

    def CallAfter(self, func, *args, **kwargs) -> None:
        """模拟 wx.CallAfter 的行为，将任务投递到 GUI 线程。"""

        self._call_after_signal.emit(func, args, kwargs)

    @staticmethod
    def _invoke(func, args, kwargs) -> None:
        func(*args, **kwargs)

    class _App:
        @staticmethod
        def ExitMainLoop() -> None:  # pragma: no cover - 兼容保留
            pass

    @staticmethod
    def GetApp():  # pragma: no cover - 兼容保留
        return _WxCompat._App()


# 暴露一个与 wx 接口兼容的对象供外部调用。
wx = _WxCompat()
