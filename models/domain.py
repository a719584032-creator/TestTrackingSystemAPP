"""Data models that mirror server side payloads."""
from __future__ import annotations

import re
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
class PlanStatistics:
    """Aggregated execution statistics for a test plan."""

    total_results: int
    executed_results: int
    passed: int
    failed: int
    blocked: int
    skipped: int
    not_run: int

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PlanStatistics":
        return cls(
            total_results=payload.get("total_results", 0),
            executed_results=payload.get("executed_results", 0),
            passed=payload.get("passed", 0),
            failed=payload.get("failed", 0),
            blocked=payload.get("blocked", 0),
            skipped=payload.get("skipped", 0),
            not_run=payload.get("not_run", 0),
        )


@dataclass(slots=True)
class PlanTester:
    """Tester assigned to a plan."""

    id: int
    name: str
    username: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PlanTester":
        tester_info = payload.get("tester") or {}
        return cls(
            id=payload.get("user_id")
            or tester_info.get("id")
            or payload.get("id")
            or 0,
            name=payload.get("name") or tester_info.get("username", ""),
            username=tester_info.get("username"),
        )

    def display_name(self) -> str:
        return self.name or (self.username or "")


@dataclass(slots=True)
class PlanExecutionRun:
    """Execution summary for a single run of a plan."""

    id: int
    name: str
    status: Optional[str]
    run_type: Optional[str]
    total: int
    executed: int
    passed: int
    failed: int
    blocked: int
    skipped: int
    not_run: int
    start_time: Optional[str]
    end_time: Optional[str]

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PlanExecutionRun":
        return cls(
            id=payload.get("id"),
            name=payload.get("name", ""),
            status=payload.get("status"),
            run_type=payload.get("run_type"),
            total=payload.get("total", 0),
            executed=payload.get("executed", 0),
            passed=payload.get("passed", 0),
            failed=payload.get("failed", 0),
            blocked=payload.get("blocked", 0),
            skipped=payload.get("skipped", 0),
            not_run=payload.get("not_run", 0),
            start_time=payload.get("start_time"),
            end_time=payload.get("end_time"),
        )


@dataclass(slots=True)
class PlanDetail:
    """Detailed information for a selected test plan."""

    id: int
    name: str
    description: Optional[str]
    department_name: Optional[str]
    project_name: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    status: Optional[str]
    testers: List[PlanTester] = field(default_factory=list)
    device_models: List[DeviceModel] = field(default_factory=list)
    statistics: Optional[PlanStatistics] = None
    execution_runs: List[PlanExecutionRun] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PlanDetail":
        return cls(
            id=payload.get("id"),
            name=payload.get("name", ""),
            description=payload.get("description"),
            department_name=payload.get("department_name"),
            project_name=payload.get("project_name"),
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
            status=payload.get("status"),
            testers=[PlanTester.from_dict(item) for item in payload.get("testers", [])],
            device_models=[DeviceModel.from_dict(item) for item in payload.get("device_models", [])],
            statistics=PlanStatistics.from_dict(payload.get("statistics", {}))
            if payload.get("statistics")
            else None,
            execution_runs=[
                PlanExecutionRun.from_dict(item) for item in payload.get("execution_runs", [])
            ],
        )

    def tester_names(self) -> List[str]:
        names: List[str] = []
        for tester in self.testers:
            name = tester.display_name()
            if name:
                names.append(name)
        return names


@dataclass(slots=True)
class CaseExecutionResult:
    """Represents a single execution run for a plan case."""

    id: Optional[int]
    plan_case_id: Optional[int]
    plan_device_model_id: Optional[int]
    device_model_id: Optional[int]
    device_model_name: Optional[str]
    device_model_code: Optional[str]
    result: str
    executed_at: Optional[str]
    executed_by: Optional[int]
    executed_by_name: Optional[str]
    remark: Optional[str]
    failure_reason: Optional[str]
    bug_ref: Optional[str]
    run_id: Optional[int]
    duration_ms: Optional[int]
    device_model: Optional[DeviceModel]

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CaseExecutionResult":
        device_payload = payload.get("device_model") or {}
        if not device_payload and payload.get("device_model_id"):
            device_payload = {
                "id": payload.get("device_model_id"),
                "name": payload.get("device_model_name"),
                "model_code": payload.get("device_model_code"),
            }

        device = DeviceModel.from_dict(device_payload) if device_payload else None

        return cls(
            id=payload.get("id"),
            plan_case_id=payload.get("plan_case_id"),
            plan_device_model_id=payload.get("plan_device_model_id"),
            device_model_id=payload.get("device_model_id") or device.id if device else None,
            device_model_name=payload.get("device_model_name")
            or device_payload.get("name")
            if device_payload
            else None,
            device_model_code=payload.get("device_model_code")
            or device_payload.get("model_code")
            if device_payload
            else None,
            result=payload.get("result", "pending"),
            executed_at=payload.get("executed_at"),
            executed_by=payload.get("executed_by"),
            executed_by_name=payload.get("executed_by_name"),
            remark=payload.get("remark"),
            failure_reason=payload.get("failure_reason"),
            bug_ref=payload.get("bug_ref"),
            run_id=payload.get("run_id"),
            duration_ms=payload.get("duration_ms"),
            device_model=device,
        )


@dataclass(slots=True)
class CaseStep:
    """Represents a single step within a plan case."""

    no: Optional[int]
    action: Optional[str]
    expected: Optional[str]
    keyword: Optional[str]
    note: Optional[str]

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CaseStep":
        return cls(
            no=payload.get("no"),
            action=payload.get("action"),
            expected=payload.get("expected"),
            keyword=payload.get("keyword"),
            note=payload.get("note"),
        )


@dataclass(slots=True)
class PlanCase:
    """Model for the `/test-plans/{plan}/cases` endpoint."""

    id: int
    case_id: int
    title: str
    priority: Optional[str]
    latest_result: Optional[str]
    preconditions: Optional[str]
    expected_result: Optional[str]
    include: bool
    require_all_devices: bool
    order_no: Optional[int]
    plan_id: Optional[int]
    keywords: List[str] = field(default_factory=list)
    group_path: Optional[str] = None
    workload_minutes: Optional[int] = None
    execution_results: List[CaseExecutionResult] = field(default_factory=list)
    device_models: List[DeviceModel] = field(default_factory=list)
    steps: List[CaseStep] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PlanCase":
        return cls(
            id=payload.get("id"),
            case_id=payload.get("case_id"),
            title=payload.get("title", ""),
            priority=payload.get("priority"),
            latest_result=payload.get("latest_result"),
            preconditions=payload.get("preconditions"),
            expected_result=payload.get("expected_result"),
            include=payload.get("include", True),
            require_all_devices=payload.get("require_all_devices", False),
            order_no=payload.get("order_no"),
            plan_id=payload.get("plan_id"),
            keywords=list(payload.get("keywords") or []),
            group_path=payload.get("group_path"),
            workload_minutes=payload.get("workload_minutes"),
            execution_results=[
                CaseExecutionResult.from_dict(result)
                for result in payload.get("execution_results", [])
            ],
            device_models=_collect_device_models(payload),
            steps=[CaseStep.from_dict(step) for step in payload.get("steps", [])],
        )

    def keyword_actions(self) -> List[str]:
        """Return a sanitized list of keyword tokens."""

        return [
            token
            for token in self.keyword_tokens()
            if "+" in token
        ]

    def keyword_tokens(self) -> List[str]:
        """Return flattened keyword tokens for display and parsing."""

        tokens: List[str] = []
        splitter = re.compile(r"[\s,;，；]+")
        for raw in self.keywords:
            if not raw:
                continue
            if isinstance(raw, str):
                parts = splitter.split(raw.strip())
            else:  # pragma: no cover - 防御性分支
                parts = [str(raw)]
            for part in parts:
                part = part.strip()
                if part:
                    tokens.append(part)
        return tokens

    def display_keywords(self) -> str:
        """Return keywords formatted for UI display."""

        return " ".join(self.keyword_tokens())


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
