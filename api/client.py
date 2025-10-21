"""HTTP client that communicates with the PATVS backend."""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, Iterable, List, Optional

import requests

from ..config import API_CONFIG
from ..models import (
    Department,
    ExecutionPayload,
    Plan,
    PlanCase,
    Project,
)

LOGGER = logging.getLogger(__name__)


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self) -> None:
        self._session = requests.Session()
        self._token: Optional[str] = None

    # ------------------------------------------------------------------
    # Authentication
    def authenticate(self, username: str, password: str) -> Dict[str, Any]:
        url = f"{API_CONFIG.base_url}/auth/login"
        response = self._session.post(
            url,
            json={"username": username, "password": password},
            timeout=API_CONFIG.timeout_seconds,
        )
        payload = self._ensure_ok(response)
        token = payload["data"]["token"]
        self.set_token(token)
        return payload["data"]

    def set_token(self, token: Optional[str]) -> None:
        self._token = token
        if token:
            self._session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            self._session.headers.pop("Authorization", None)

    # ------------------------------------------------------------------
    # Fetch metadata
    def get_departments(self) -> List[Department]:
        payload = self._get("/departments", params={"page": 1, "page_size": 1000})
        return [Department(**item) for item in payload["data"]["items"]]

    def get_projects(self, department_id: int) -> List[Project]:
        payload = self._get(
            "/projects",
            params={"page": 1, "page_size": 1000, "department_id": department_id},
        )
        return [Project(**item) for item in payload["data"]["items"]]

    def get_plans(self, department_id: int, project_id: int) -> List[Plan]:
        payload = self._get(
            "/test-plans",
            params={
                "department_id": department_id,
                "project_id": project_id,
                "page": 1,
                "page_size": 1000,
            },
        )
        plans = []
        for item in payload["data"]["items"]:
            item.setdefault("execution_runs", [])
            plans.append(Plan(**item))
        return plans

    def get_plan_cases(
        self,
        plan_id: int,
        directory: Optional[str] = None,
        device_model: Optional[str] = None,
        priority: Optional[str] = None,
        result: Optional[str] = None,
    ) -> List[PlanCase]:
        params: Dict[str, Any] = {}
        if directory:
            params["directory"] = directory
        if device_model:
            params["device_model"] = device_model
        if priority:
            params["priority"] = priority
        if result:
            params["result"] = result
        payload = self._get(f"/test-plans/{plan_id}/cases", params=params)
        cases: List[PlanCase] = []
        for item in payload["data"]["cases"]:
            item.setdefault("execution_results", [])
            cases.append(PlanCase(**item))
        return cases

    # ------------------------------------------------------------------
    def post_execution_result(self, plan_id: int, payload: ExecutionPayload) -> Dict[str, Any]:
        url = f"{API_CONFIG.base_url}/test-plans/{plan_id}/results"
        response = self._session.post(
            url,
            json=self._payload_to_dict(payload),
            timeout=API_CONFIG.timeout_seconds,
        )
        return self._ensure_ok(response)

    # ------------------------------------------------------------------
    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{API_CONFIG.base_url}{path}"
        response = self._session.get(url, params=params, timeout=API_CONFIG.timeout_seconds)
        return self._ensure_ok(response)

    @staticmethod
    def _payload_to_dict(payload: ExecutionPayload) -> Dict[str, Any]:
        data = asdict(payload)
        data["attachments"] = [asdict(attachment) for attachment in payload.attachments]
        return data

    @staticmethod
    def _ensure_ok(response: requests.Response) -> Dict[str, Any]:
        try:
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:  # pragma: no cover - network failure
            LOGGER.error("API request failed: %s", exc)
            raise ApiError(str(exc)) from exc
        except ValueError as exc:  # pragma: no cover - invalid JSON
            LOGGER.error("Invalid JSON response: %s", exc)
            raise ApiError("Invalid JSON response") from exc
        if payload.get("code") not in (200, "success"):
            raise ApiError(payload.get("message", "Unknown API error"))
        return payload
