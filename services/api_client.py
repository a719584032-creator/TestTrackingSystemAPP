"""与 TTS 后端交互的 HTTP 接口封装。"""
from __future__ import annotations

import json
import logging
import os
import mimetypes
import re
import urllib.parse
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests

from config.settings import SETTINGS
from models import (
    Department,
    PlanCaseQueryResult,
    PlanDetail,
    Project,
    TestPlan,
)
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
        payload = self._request("GET", "/feiyan/departments", params={"page": 1, "page_size": 1000})
        return [Department.from_dict(item) for item in payload.get("data", {}).get("items", [])]

    def get_projects(self, department_id: str) -> List[Project]:
        payload = self._request(
            "GET",
            "/feiyan/projects",
            params={"page": 1, "page_size": 1000, "department_id": department_id},
        )
        return [Project.from_dict(item) for item in payload.get("data", {}).get("items", [])]

    def get_test_plans(self, department_id: str, project_id: str) -> List[TestPlan]:
        payload = self._request(
            "GET",
            "/feiyan/test-plans",
            params={
                "department_id": department_id,
                "project_id": project_id,
                "page": 1,
                "page_size": 100,
            },
        )
        items = payload.get("data", {}).get("items", [])
        return [TestPlan.from_dict(item) for item in items]

    def get_plan_detail(self, plan_id: str) -> PlanDetail:
        payload = self._request("GET", f"/feiyan/test-plans/{plan_id}")
        return PlanDetail.from_dict(payload.get("data", {}))

    def import_test_plan(self, file_path: str) -> Dict[str, Any]:
        if not file_path:
            raise ValueError("File path is required")
        url = f"{self.base_url}/feiyan/test-plans/import"
        file_name = os.path.basename(file_path)
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        self._log_request("POST", url, None, {"file": file_name, "mime_type": mime_type})
        try:
            with open(file_path, "rb") as handle:
                response = requests.post(
                    url,
                    headers=self._headers(),
                    files={"file": (file_name, handle, mime_type)},
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )
        except requests.RequestException as exc:
            logger.exception("Network error while calling %s", url)
            raise NetworkError(str(exc)) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            logger.exception("Non JSON response from %s", url)
            raise ClientError("服务端响应格式异常") from exc

        self._log_response("POST", url, response.status_code, payload)
        if response.status_code == 401:
            raise AuthenticationError(payload.get("message", "未授权"))
        if response.status_code >= 400:
            raise ClientError(payload.get("message", f"请求失败: {response.status_code}"))
        return payload

    def export_test_plan(self, plan_id: str) -> Tuple[Optional[bytes], Optional[str], Optional[Dict[str, Any]]]:
        url = f"{self.base_url}/feiyan/test-plans/{plan_id}/export"
        self._log_request("GET", url, None, None)
        try:
            response = requests.get(
                url,
                headers=self._headers(),
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
        except requests.RequestException as exc:
            logger.exception("Network error while calling %s", url)
            raise NetworkError(str(exc)) from exc

        content_type = (response.headers.get("Content-Type") or "").lower()
        if response.status_code == 401:
            message = "Unauthorized"
            try:
                payload = response.json()
                message = payload.get("message", message)
                self._log_response("GET", url, response.status_code, payload)
            except ValueError:
                logger.info("API response GET %s status=%s", url, response.status_code)
            raise AuthenticationError(message)

        if response.status_code >= 400:
            message = f"Request failed: {response.status_code}"
            try:
                payload = response.json()
                message = payload.get("message", message)
                data = payload.get("data")
                details = []
                if isinstance(data, dict):
                    if "failure_count" in data:
                        details.append(f"failure_count: {data.get('failure_count')}")
                    errors = data.get("errors")
                    if errors:
                        details.append(f"errors: {errors}")
                if details:
                    message = f"{message}\n" + "\n".join(details)
                self._log_response("GET", url, response.status_code, payload)
            except ValueError:
                logger.info("API response GET %s status=%s", url, response.status_code)
            raise ClientError(message)

        if "application/json" in content_type:
            try:
                payload = response.json()
            except ValueError as exc:
                logger.exception("Non JSON response from %s", url)
                raise ClientError("Server response is not JSON") from exc
            self._log_response("GET", url, response.status_code, payload)
            return None, None, payload

        payload = None
        if response.content:
            stripped = response.content.lstrip()
            if stripped.startswith(b"{") or stripped.startswith(b"["):
                try:
                    payload = response.json()
                except ValueError:
                    payload = None
        if payload is not None:
            self._log_response("GET", url, response.status_code, payload)
            return None, None, payload

        filename = self._extract_filename(response.headers.get("Content-Disposition"))
        content = response.content
        self._log_response(
            "GET",
            url,
            response.status_code,
            {"filename": filename, "size": len(content)},
        )
        return content, filename, None

    def get_plan_cases(
        self,
        plan_id: str,
        *,
        group_path: Optional[str] = None,
        device_id: Optional[str] = None,
        status: Optional[str] = None,
        page_size: int = 1000,
    ) -> PlanCaseQueryResult:
        params: Dict[str, Any] = {"page": 1, "page_size": page_size}
        if group_path:
            params["group_path"] = group_path
        if device_id:
            params["device_id"] = device_id
        if status:
            params["status"] = status
        payload = self._request("GET", f"/feiyan/test-plans/{plan_id}/cases", params=params)
        return PlanCaseQueryResult.from_payload(payload)

    def create_display_matrix_cases(
        self, plan_id: str, cases: Sequence[Dict[str, Any]]
    ) -> Dict[str, Any]:
        body = {"cases": list(cases)}
        return self._request(
            "POST",
            f"/feiyan/test-plans/{plan_id}/display-matrix-cases",
            json=body,
        )

    def submit_result(
        self,
        plan_id: str,
        case_id_ext: str,
        result: str,
        remark: str = "",
        bug_ref: str | None = None,
        attachments: Optional[Iterable[Dict[str, str]]] = None,
        *,
        execution_start_time: str,
        execution_end_time: str,
    ) -> Dict[str, any]:
        if not execution_start_time or not execution_end_time:
            raise ValueError("Execution start/end time is required")
        if not case_id_ext:
            raise ValueError("Case ID is required")
        body: Dict[str, any] = {
            "case_id_ext": case_id_ext,
            "run_result": result,
            "execution_start_time": execution_start_time,
            "execution_end_time": execution_end_time,
            "remark": remark,
        }
        if bug_ref:
            body["bug_ref"] = bug_ref
        if attachments:
            body["attachments"] = self._upload_attachments(plan_id, case_id_ext, attachments)
        response = self._request("POST", f"/feiyan/test-plans/{plan_id}/results", json=body)
        return response

    def _upload_attachments(
        self,
        plan_id: str,
        case_id_ext: str,
        attachments: Iterable[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        prepared: List[Dict[str, Any]] = []
        for attachment in attachments:
            local_path = attachment.get("local_path")
            if not local_path:
                raise ValueError("Attachment missing local path")
            file_name = attachment.get("file_name") or os.path.basename(local_path)
            mime_type = attachment.get("mime_type") or mimetypes.guess_type(local_path)[0]
            mime_type = mime_type or "application/octet-stream"
            size = attachment.get("size")
            if size is None:
                size = os.path.getsize(local_path)
            presign_payload = {
                "case_id_ext": case_id_ext,
                "file_name": file_name,
                "mime_type": mime_type,
                "size": size,
            }
            presign = self._request(
                "POST",
                f"/feiyan/test-plans/{plan_id}/attachments/presign",
                json=presign_payload,
            )
            data = presign.get("data") or {}
            upload_url = data.get("upload_url")
            headers = data.get("headers") or {}
            file_key = data.get("file_key")
            if not upload_url or not file_key:
                raise ClientError("Failed to get attachment upload URL")
            self._upload_presigned_file(upload_url, headers, local_path)
            prepared.append(
                {
                    "file_name": data.get("file_name") or file_name,
                    "file_key": file_key,
                    "mime_type": data.get("mime_type") or mime_type,
                    "size": data.get("size") or size,
                }
            )
        return prepared

    def _upload_presigned_file(self, url: str, headers: Dict[str, Any], path: str) -> None:
        try:
            with open(path, "rb") as handle:
                response = requests.put(
                    url,
                    data=handle,
                    headers={str(k): str(v) for k, v in (headers or {}).items()},
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )
        except requests.RequestException as exc:
            logger.exception("Upload error while calling %s", url)
            raise NetworkError(str(exc)) from exc

        if response.status_code >= 400:
            raise ClientError(f"Attachment upload failed: {response.status_code}")
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

    @staticmethod
    def _extract_filename(content_disposition: Optional[str]) -> Optional[str]:
        if not content_disposition:
            return None
        match = re.search(r"filename\\*=UTF-8''([^;]+)", content_disposition)
        if match:
            return urllib.parse.unquote(match.group(1))
        match = re.search(r'filename=\"?([^\";]+)\"?', content_disposition)
        if match:
            return match.group(1)
        return None

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

    def _sanitize_for_logging(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized: Dict[str, Any] = {}
            for key, item in value.items():
                key_lower = str(key).lower()
                if key_lower in {"password", "token", "authorization", "upload_url"}:
                    sanitized[key] = "<redacted>"
                elif key_lower == "headers":
                    sanitized[key] = "<redacted>"
                elif key == "attachments" and item:
                    sanitized[key] = self._attachment_log_summary(item)
                else:
                    sanitized[key] = self._sanitize_for_logging(item)
            return sanitized
        if isinstance(value, list):
            if len(value) > 3:
                head = [self._sanitize_for_logging(item) for item in value[:3]]
                head.append(f"...({len(value) - 3} more)")
                return head
            return [self._sanitize_for_logging(item) for item in value]
        return value

    def _preview_for_logging(self, value: Any, *, max_len: int = 2000) -> str:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            text = str(value)
        if len(text) > max_len:
            return f"{text[:max_len]}...(truncated)"
        return text

    def _log_request(self, method: str, url: str, params: Any, payload: Any) -> None:
        safe_params = self._sanitize_for_logging(params) if params else None
        safe_payload = self._sanitize_for_logging(payload) if payload else None
        logger.debug(
            "API request %s %s params=%s json=%s",
            method,
            url,
            self._preview_for_logging(safe_params),
            self._preview_for_logging(safe_payload),
        )

    def _log_response(self, method: str, url: str, status_code: int, payload: Any) -> None:
        safe_payload = self._sanitize_for_logging(payload)
        logger.debug(
            "API response %s %s status=%s payload=%s",
            method,
            url,
            status_code,
            self._preview_for_logging(safe_payload),
        )

    def _request(self, method: str, path: str, *, params=None, json=None, auth_request: bool = False):
        url = f"{self.base_url}{path}"
        self._log_request(method, url, params, json)
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

        self._log_response(method, url, response.status_code, payload)
        if response.status_code == 401:
            raise AuthenticationError(payload.get("message", "未授权"))
        if response.status_code >= 400:
            raise ClientError(payload.get("message", f"请求失败: {response.status_code}"))

        return payload


def encode_attachment(path: str) -> Dict[str, str]:
    """Read file metadata for attachment upload."""

    mime_type, _ = mimetypes.guess_type(path)
    mime_type = mime_type or "application/octet-stream"
    size = os.path.getsize(path)
    return {
        "file_name": os.path.basename(path),
        "mime_type": mime_type,
        "size": size,
    }
