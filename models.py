"""Data models used across the PATVS desktop client."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence


@dataclass
class Department:
    id: int
    name: str
    code: Optional[str] = None
    active: bool = True


@dataclass
class Project:
    id: int
    name: str
    department_id: int
    status: str
    description: Optional[str] = None


@dataclass
class ExecutionRun:
    id: int
    name: str
    status: str
    run_type: str
    total: int
    executed: int
    passed: int
    failed: int
    blocked: int
    not_run: int
    skipped: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@dataclass
class Plan:
    id: int
    name: str
    department_id: int
    project_id: int
    status: str
    description: Optional[str] = None
    execution_runs: Sequence[ExecutionRun] = field(default_factory=list)


@dataclass
class PlanCaseStep:
    no: int
    action: str
    expected: str
    note: str
    keyword: str


@dataclass
class ExecutionResult:
    id: int
    result: str
    executed_at: Optional[datetime]
    executed_by_name: Optional[str]
    remark: Optional[str]
    failure_reason: Optional[str]
    bug_ref: Optional[str]
    duration_ms: Optional[int]


@dataclass
class PlanCase:
    id: int
    case_id: int
    title: str
    priority: str
    group_path: str
    keywords: List[str]
    expected_result: Optional[str]
    preconditions: Optional[str]
    steps: Sequence[PlanCaseStep]
    latest_result: Optional[str]
    execution_results: Sequence[ExecutionResult] = field(default_factory=list)
    require_all_devices: bool = False
    workload_minutes: Optional[int] = None


@dataclass
class ExecutionAttachment:
    file_name: str
    content: str
    size: int


@dataclass
class ExecutionPayload:
    plan_case_id: int
    result: str
    remark: str
    failure_reason: Optional[str]
    bug_ref: Optional[str]
    execution_start_time: Optional[str]
    execution_end_time: Optional[str]
    attachments: Sequence[ExecutionAttachment] = field(default_factory=list)
    device_model_id: Optional[int] = None
    plan_device_model_id: Optional[int] = None
