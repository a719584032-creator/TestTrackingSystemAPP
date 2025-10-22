"""Data models that mirror server side payloads."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class Department:
    """Represents a testing department."""

    id: int
    name: str
    active: bool = True
    code: Optional[str] = None
    description: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Department":
        return cls(
            id=payload.get("id"),
            name=payload.get("name", ""),
            active=payload.get("active", True),
            code=payload.get("code"),
            description=payload.get("description"),
        )


@dataclass(slots=True)
class Project:
    """Represents a project under a department."""

    id: int
    name: str
    department_id: int
    status: str

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Project":
        return cls(
            id=payload.get("id"),
            name=payload.get("name", ""),
            department_id=payload.get("department_id"),
            status=payload.get("status", "unknown"),
        )


@dataclass(slots=True)
class DeviceModel:
    """Represents a device model associated with a test plan."""

    id: int
    name: str
    model_code: Optional[str]
    category: Optional[str]

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "DeviceModel":
        return cls(
            id=payload.get("device_model_id") or payload.get("id"),
            name=payload.get("name")
            or payload.get("device_model", {}).get("name", ""),
            model_code=payload.get("model_code")
            or payload.get("device_model", {}).get("model_code"),
            category=payload.get("category")
            or payload.get("device_model", {}).get("category"),
        )


@dataclass(slots=True)
class TestPlan:
    """Lightweight representation of a test plan."""

    id: int
    name: str
    project_id: int
    department_id: int

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TestPlan":
        return cls(
            id=payload.get("id"),
            name=payload.get("name", ""),
            project_id=payload.get("project_id"),
            department_id=payload.get("department_id"),
        )


@dataclass(slots=True)
class CaseExecutionResult:
    """Represents a single execution run for a plan case."""

    result: str
    executed_at: Optional[str]
    executed_by_name: Optional[str]
    duration_ms: Optional[int]

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CaseExecutionResult":
        return cls(
            result=payload.get("result", "pending"),
            executed_at=payload.get("executed_at"),
            executed_by_name=payload.get("executed_by_name"),
            duration_ms=payload.get("duration_ms"),
        )


@dataclass(slots=True)
class PlanCase:
    """Model for the `/test-plans/{plan}/cases` endpoint."""

    id: int
    case_id: int
    title: str
    priority: Optional[str]
    latest_result: Optional[str]
    keywords: List[str] = field(default_factory=list)
    group_path: Optional[str] = None
    workload_minutes: Optional[int] = None
    execution_results: List[CaseExecutionResult] = field(default_factory=list)
    device_models: List[DeviceModel] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PlanCase":
        return cls(
            id=payload.get("id"),
            case_id=payload.get("case_id"),
            title=payload.get("title", ""),
            priority=payload.get("priority"),
            latest_result=payload.get("latest_result"),
            keywords=list(payload.get("keywords") or []),
            group_path=payload.get("group_path"),
            workload_minutes=payload.get("workload_minutes"),
            execution_results=[
                CaseExecutionResult.from_dict(result)
                for result in payload.get("execution_results", [])
            ],
            device_models=_collect_device_models(payload),
        )

    def keyword_actions(self) -> List[str]:
        """Return a sanitized list of keyword tokens."""

        return [token.strip() for token in self.keywords if token]


def _collect_device_models(payload: Dict[str, Any]) -> List[DeviceModel]:
    seen: dict[int, DeviceModel] = {}
    for exec_result in payload.get("execution_results", []):
        device_payload = exec_result.get("device_model") or {}
        if not device_payload and exec_result.get("device_model_id"):
            device_payload = {
                "id": exec_result.get("device_model_id"),
                "name": exec_result.get("device_model_name"),
                "model_code": exec_result.get("device_model_code"),
                "category": exec_result.get("device_model_category"),
            }
        if not device_payload:
            continue
        model = DeviceModel.from_dict(device_payload)
        seen[model.id] = model
    for device_payload in payload.get("device_models", []):
        model = DeviceModel.from_dict(device_payload)
        seen[model.id] = model
    return list(seen.values())
