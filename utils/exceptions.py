"""应用中通用的异常类定义。"""
from __future__ import annotations


class ClientError(Exception):
    """可恢复的客户端错误的基础异常类型。"""


class AuthenticationError(ClientError):
    """当远程服务拒绝用户凭据时抛出的异常。"""


class ValidationError(ClientError):
    """当 UI 层检测到无效用户输入时抛出的异常。"""


class NetworkError(ClientError):
    """当 HTTP 请求无法完成时抛出的异常。"""


class UpdateError(ClientError):
    """当 OTA 更新流程失败时抛出的异常。"""

