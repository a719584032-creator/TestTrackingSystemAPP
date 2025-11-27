"""与 TTS 后端交互的 HTTP 接口封装。"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests

from config.settings import SETTINGS
from models import Department, PlanCase, PlanDetail, Project, TestPlan
from utils.exceptions import AuthenticationError, ClientError, NetworkError
from utils.security import encode_timestamp_token

logger = logging.getLogger(__name__)


class ApiClient:
    """ TTS 后端 REST 接口封装 """

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        client_settings = SETTINGS
        settings = client_settings.api
        self.base_url = base_url or settings.base_url.rstrip("/")
        self.timeout = timeout or settings.timeout
        self.verify_ssl = settings.verify_ssl
        self._time_secret = client_settings.crypto.result_time_secret
        self._token: Optional[str] = None

    # ------------------------------------------------------------------
    # 认证相关辅助方法
    # ------------------------------------------------------------------
    def authenticate(self, username: str, password: str) -> Dict[str, any]:
        """调用登录接口完成用户名密码认证。"""

        response = self._request(
            "POST",
            "/auth/login",
            json={"username": username, "password": password},
            auth_request=True,
        )
        data = response.get("data", {})
        token = data.get("token")
        if not token:
            raise AuthenticationError("登录响应缺少 token")
        self._token = token  # 登录成功后缓存 token，供后续请求携带
        return data

    def set_token(self, token: Optional[str]) -> None:
        self._token = token

    # ------------------------------------------------------------------
    # 业务查询辅助方法
    # ------------------------------------------------------------------
    def get_departments(self) -> List[Department]:
        payload = self._request("GET", "/departments", params={"page": 1, "page_size": 1000})
        return [Department.from_dict(item) for item in payload.get("data", {}).get("items", [])]

    def get_projects(self, department_id: int) -> List[Project]:
        payload = self._request(
            "GET",
            "/projects",
            params={"page": 1, "page_size": 1000, "department_id": department_id},
        )
        return [Project.from_dict(item) for item in payload.get("data", {}).get("items", [])]

    def get_test_plans(self, department_id: int, project_id: int) -> List[TestPlan]:
        payload = self._request(
            "GET",
            "/test-plans",
            params={
                "department_id": department_id,
                "project_id": project_id,
                "page": 1,
                "page_size": 100,
            },
        )
        return [TestPlan.from_dict(item) for item in payload.get("data", {}).get("items", [])]

    def get_plan_detail(self, plan_id: int) -> PlanDetail:
        payload = self._request("GET", f"/test-plans/{plan_id}")
        return PlanDetail.from_dict(payload.get("data", {}))

    def get_plan_cases(self, plan_id: int) -> List[PlanCase]:
        payload = self._request("GET", f"/test-plans/{plan_id}/cases")
        cases = payload.get("data", {}).get("cases", [])
        return [PlanCase.from_dict(case) for case in cases]

    def submit_result(
        self,
        plan_id: int,
        plan_case_id: int,
        result: str,
        remark: str = "",
        failure_reason: str | None = None,
        bug_ref: str | None = None,
        device_model_id: int | None = None,
        plan_device_model_id: int | None = None,
        attachments: Optional[Iterable[Dict[str, str]]] = None,
        *,
        execution_start_time: str,
        execution_end_time: str,
    ) -> Dict[str, any]:
        # 后端要求带上加密后的开始/结束时间
        if not execution_start_time or not execution_end_time:
            raise ValueError("执行结果开始/结束时间不能为空")
        body: Dict[str, any] = {
            "plan_case_id": plan_case_id,
            "result": result,
            "remark": remark,
        }
        if failure_reason:
            body["failure_reason"] = failure_reason
        if bug_ref:
            body["bug_ref"] = bug_ref
        if device_model_id:
            body["device_model_id"] = device_model_id
        if plan_device_model_id:
            body["plan_device_model_id"] = plan_device_model_id
        if attachments:
            body["attachments"] = list(attachments)
        encrypted_start = self._encrypt_time_value(execution_start_time)
        encrypted_end = self._encrypt_time_value(execution_end_time)
        body["execution_start_time"] = encrypted_start
        body["execution_end_time"] = encrypted_end
        time_parameters: List[Tuple[str, str, str]] = [
            ("execution_start_time", execution_start_time, encrypted_start),
            ("execution_end_time", execution_end_time, encrypted_end),
        ]

        self._log_time_parameters(time_parameters)
        # logger.info(
        #     "提交结果请求参数(plan_id=%s, plan_case_id=%s): %s",
        #     plan_id,
        #     plan_case_id,
        #     self._submission_payload_for_logging(body),
        # )
        response = self._request("POST", f"/test-plans/{plan_id}/results", json=body)
        # logger.info(
        #     "提交结果响应(plan_id=%s, plan_case_id=%s): %s",
        #     plan_id,
        #     plan_case_id,
        #     response,
        # )
        return response

    # ------------------------------------------------------------------
    def _submission_payload_for_logging(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """附件字段仅保留概要，避免日志体积过大。"""
        sanitized: Dict[str, Any] = {}
        for key, value in payload.items():
            if key == "attachments" and value:
                sanitized[key] = self._attachment_log_summary(value)
            else:
                sanitized[key] = value
        return sanitized

    def _log_time_parameters(
        self, params: Sequence[Tuple[str, str, str]]
    ) -> None:
        for field, raw_value, encrypted_value in params:
            logger.debug(
                "时间参数 %s: 原始=%s, 加密=%s",
                field,
                raw_value,
                encrypted_value,
            )

    @staticmethod
    def _attachment_log_summary(attachments: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        summary: List[Dict[str, Any]] = []
        for attachment in attachments:
            summary.append(
                {
                    "file_name": attachment.get("file_name"),
                    "size": attachment.get("size"),
                }
            )
        return summary

    def _encrypt_time_value(self, value: str) -> str:
        if not value:
            raise ValueError("执行结果时间不能为空")
        if not self._time_secret:
            raise ValueError("提交结果密钥未配置，请联系管理员")
        # 时间戳采用后端约定的加密方式，防止被篡改
        return encode_timestamp_token(value, self._time_secret)

    # ------------------------------------------------------------------
    # 内部通用工具
    # ------------------------------------------------------------------
    def _headers(self, auth_request: bool = False) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if not auth_request and self._token:
            headers["Authorization"] = f"Bearer {self._token}"  # 业务请求统一带上 token
        return headers

    def _request(self, method: str, path: str, *, params=None, json=None, auth_request: bool = False):
        url = f"{self.base_url}{path}"
        try:
            # 统一入口发起 HTTP 请求，便于处理超时和 SSL 校验
            response = requests.request(
                method,
                url,
                headers=self._headers(auth_request=auth_request),
                params=params,
                json=json,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
        except requests.RequestException as exc:  # pragma: no cover - 网络异常兜底
            logger.exception("Network error while calling %s", url)
            raise NetworkError(str(exc)) from exc

        try:
            # 后端约定返回 JSON，无法解析则视为错误响应
            payload = response.json()
        except ValueError as exc:  # pragma: no cover - 防御性兜底
            logger.exception("Non JSON response from %s", url)
            raise ClientError("服务器响应格式异常") from exc

        if response.status_code == 401:
            raise AuthenticationError(payload.get("message", "未授权"))
        if response.status_code >= 400:
            raise ClientError(payload.get("message", f"请求失败: {response.status_code}"))

        return payload


def encode_attachment(path: str) -> Dict[str, str]:
    """读取文件并返回接口可接受的附件 payload。"""

    with open(path, "rb") as handle:
        binary = handle.read()
    content = base64.b64encode(binary).decode("ascii")
    return {
        "file_name": os.path.basename(path),
        "content": f"data:image/png;base64,{content}",
        "size": len(binary),
    }
