"""HTTP client responsible for interacting with the TTS backend."""
from __future__ import annotations

import base64
import logging
import os
from typing import Dict, Iterable, List, Optional

import requests

from config.settings import SETTINGS
from models import Department, PlanCase, PlanDetail, Project, TestPlan
from utils.exceptions import AuthenticationError, ClientError, NetworkError

logger = logging.getLogger(__name__)


class ApiClient:
    """Simple wrapper around the REST endpoints exposed by TTS."""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        settings = SETTINGS.api
        self.base_url = base_url or settings.base_url.rstrip("/")
        self.timeout = timeout or settings.timeout
        self._token: Optional[str] = None

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------
    def authenticate(self, username: str, password: str) -> Dict[str, any]:
        """Authenticate ``username`` using the login endpoint."""

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
        self._token = token
        return data

    def set_token(self, token: Optional[str]) -> None:
        self._token = token

    # ------------------------------------------------------------------
    # Fetch helpers
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
        execution_start_time: Optional[str] = None,
        execution_end_time: Optional[str] = None,
    ) -> Dict[str, any]:
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
        if execution_start_time:
            body["execution_start_time"] = execution_start_time
        if execution_end_time:
            body["execution_end_time"] = execution_end_time

        return self._request("POST", f"/test-plans/{plan_id}/results", json=body)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _headers(self, auth_request: bool = False) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if not auth_request and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _request(self, method: str, path: str, *, params=None, json=None, auth_request: bool = False):
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method,
                url,
                headers=self._headers(auth_request=auth_request),
                params=params,
                json=json,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:  # pragma: no cover - network safety net
            logger.exception("Network error while calling %s", url)
            raise NetworkError(str(exc)) from exc

        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover - defensive
            logger.exception("Non JSON response from %s", url)
            raise ClientError("服务器响应格式异常") from exc

        if response.status_code == 401:
            raise AuthenticationError(payload.get("message", "未授权"))
        if response.status_code >= 400:
            raise ClientError(payload.get("message", f"请求失败: {response.status_code}"))

        return payload


def encode_attachment(path: str) -> Dict[str, str]:
    """Read *path* and return an API compatible attachment payload."""

    with open(path, "rb") as handle:
        binary = handle.read()
    content = base64.b64encode(binary).decode("ascii")
    return {
        "file_name": os.path.basename(path),
        "content": f"data:image/png;base64,{content}",
        "size": len(binary),
    }
