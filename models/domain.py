"""服务端数据模型参数"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class Department:
    """获取部门信息"""

    id: Optional[str]
    name: str
    active: bool = True
    code: Optional[str] = None
    description: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Department":
        raw_id = payload.get("department_id")
        return cls(
            id=str(raw_id) if raw_id is not None else None,
            name=str(payload.get("department_name") or ""),
            active=True,
            code=None,
            description=None,
        )


@dataclass(slots=True)
class Project:
    """获取部门项目信息"""

    id: Optional[str]
    name: str
    department_id: Optional[str]
    department_name: Optional[str] = None
    status: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Project":
        raw_id = payload.get("project_id")
        raw_department_id = payload.get("department_id")
        return cls(
            id=str(raw_id) if raw_id is not None else None,
            name=str(payload.get("project_name") or ""),
            department_id=str(raw_department_id) if raw_department_id is not None else None,
            department_name=payload.get("department_name"),
            status=payload.get("status"),
        )


@dataclass(slots=True)
class DeviceModel:
    """获取部门机型"""

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
    """获取测试计划"""

    id: Optional[str]
    name: str
    project_id: Optional[str]
    department_id: Optional[str]
    status: Optional[str]
    department_name: Optional[str] = None
    project_name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    passed: Optional[int] = None
    failed: Optional[int] = None
    blocked: Optional[int] = None
    not_run: Optional[int] = None
    total: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    tester_names: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TestPlan":
        raw_id = payload.get("plan_id")
        raw_project_id = payload.get("project_id")
        raw_department_id = payload.get("department_id")
        return cls(
            id=str(raw_id) if raw_id is not None else None,
            name=str(payload.get("name") or ""),
            project_id=str(raw_project_id) if raw_project_id is not None else None,
            department_id=str(raw_department_id) if raw_department_id is not None else None,
            status=payload.get("status"),
            department_name=payload.get("department_name"),
            project_name=payload.get("project_name"),
            start_time=payload.get("start_time"),
            end_time=payload.get("end_time"),
            passed=payload.get("passed"),
            failed=payload.get("failed"),
            blocked=payload.get("blocked"),
            not_run=payload.get("not_run"),
            total=payload.get("total"),
            created_at=payload.get("created_at"),
            updated_at=payload.get("updated_at"),
            tester_names=payload.get("tester_names"),
        )


@dataclass(slots=True)
class GroupTreeNode:
    """用例分组树节点。"""

    name: str
    path: str
    children: List["GroupTreeNode"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> Optional["GroupTreeNode"]:
        if not isinstance(payload, dict):
            return None
        raw_children = payload.get("children") or []
        children: List[GroupTreeNode] = []
        if isinstance(raw_children, list):
            for child in raw_children:
                if not isinstance(child, dict):
                    continue
                node = cls.from_dict(child)
                if node is not None:
                    children.append(node)
        return cls(
            name=str(payload.get("name") or ""),
            path=str(payload.get("path") or ""),
            children=children,
        )


@dataclass(slots=True)
class PlanStatistics:
    """测试计划进度详情"""

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
    """测试计划测试人员"""

    id: Optional[str]
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
    """测试计划执行记录详情"""

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
            id=str(payload.get("id")) if payload.get("id") is not None else None,
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
class PlanDevice:
    """测试计划设备"""

    id: Optional[str]
    name: str

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PlanDevice":
        raw_id = payload.get("device_id")
        return cls(
            id=str(raw_id) if raw_id is not None else None,
            name=str(payload.get("device_name") or ""),
        )


@dataclass(slots=True)
class PlanDetail:
    """选中测试计划的详细信息。"""

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
    devices: List[PlanDevice] = field(default_factory=list)
    statistics: Optional[PlanStatistics] = None
    execution_runs: List[PlanExecutionRun] = field(default_factory=list)
    dock_nine_gird: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PlanDetail":
        dock_nine_gird = _normalize_nine_grid(payload.get("dock_nine_gird"))
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
            devices=[PlanDevice.from_dict(item) for item in payload.get("devices", [])],
            statistics=PlanStatistics.from_dict(payload.get("statistics", {}))
            if payload.get("statistics")
            else None,
            execution_runs=[
                PlanExecutionRun.from_dict(item) for item in payload.get("execution_runs", [])
            ],
            dock_nine_gird=dock_nine_gird,
        )

    def tester_names(self) -> List[str]:
        names: List[str] = []
        for tester in self.testers:
            name = tester.display_name()
            if name:
                names.append(name)
        return names


def _normalize_nine_grid(raw: Any) -> Dict[str, float]:
    """Normalize nine-grid config values."""

    if not isinstance(raw, dict):
        return {}
    normalized: Dict[str, float] = {}
    for key, value in raw.items():
        if key is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        normalized[str(key)] = numeric
    return normalized


@dataclass(slots=True)
class CaseExecutionResult:
    """记录用例结果"""

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
        # 部分响应只带设备 ID/名称，需补齐成标准字段结构
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
    """计划用例步骤"""

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
    """`/test-plans/{plan}/cases` 接口返回的用例模型。"""

    id: Optional[int]
    case_id: Optional[str]
    title: str
    priority: Optional[str]
    latest_result: Optional[str]
    preconditions: Optional[str]
    expected_result: Optional[str]
    device_id: Optional[str]
    device_name: Optional[str]
    include: bool
    compatibility_testing: bool
    order_no: Optional[int]
    plan_id: Optional[str]
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
            case_id=str(payload.get("case_id")) if payload.get("case_id") is not None else None,
            title=payload.get("title", ""),
            priority=payload.get("priority"),
            latest_result=payload.get("run_result") or payload.get("latest_result"),
            preconditions=payload.get("preconditions"),
            expected_result=payload.get("expected_result"),
            device_id=str(payload.get("device_id")) if payload.get("device_id") is not None else None,
            device_name=payload.get("device_name"),
            include=payload.get("include", True),
            compatibility_testing=bool(payload.get("compatibility_testing", False)),
            order_no=payload.get("order_no"),
            plan_id=str(payload.get("plan_id")) if payload.get("plan_id") is not None else None,
            keywords=_normalize_keywords(payload.get("keywords")),
            group_path=payload.get("group_path"),
            workload_minutes=payload.get("workload_minutes"),
            execution_results=[
                CaseExecutionResult.from_dict(result)
                for result in payload.get("execution_results", [])
            ],
            device_models=_collect_device_models(payload),
            steps=_normalize_steps(payload.get("steps")),
        )

    def keyword_actions(self) -> List[str]:
        """返回过滤后的关键字 token 列表。"""

        return [
            token
            for token in self.keyword_tokens()
            if "+" in token
        ]

    def keyword_tokens(self) -> List[str]:
        """返回用于展示/解析的扁平化关键字 token。"""

        tokens: List[str] = []
        splitter = re.compile(r"[\s,;，；]+")
        for raw in self.keywords:
            if not raw:
                continue
            # 同一字段可能包含多个关键字，按空白/逗号/分号切分
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
        """格式化关键字供 UI 展示。"""

        return " ".join(self.keyword_tokens())


@dataclass(slots=True)
class PlanCaseQueryResult:
    """用例查询响应模型。"""

    items: List[PlanCase] = field(default_factory=list)
    group_tree: Optional[GroupTreeNode] = None
    total: int = 0
    page: int = 1
    page_size: int = 0

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "PlanCaseQueryResult":
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        raw_items = data.get("items")
        if raw_items is None:
            raw_items = data.get("cases", [])
        items = [PlanCase.from_dict(item) for item in raw_items or []]
        raw_tree = data.get("group_tree")
        group_tree = (
            GroupTreeNode.from_dict(raw_tree) if isinstance(raw_tree, dict) else None
        )
        return cls(
            items=items,
            group_tree=group_tree,
            total=int(data.get("total", 0) or 0),
            page=int(data.get("page", 1) or 1),
            page_size=int(data.get("page_size", 0) or 0),
        )


def _collect_device_models(payload: Dict[str, Any]) -> List[DeviceModel]:
    """ 获取计划所有机型（去重归一） """
    seen: dict[int, DeviceModel] = {}
    for exec_result in payload.get("execution_results", []):
        device_payload = exec_result.get("device_model") or {}
        # 执行结果中的设备信息优先补齐，避免丢失历史关联机型
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
        # 合并来自计划/执行记录的机型列表，后写入的覆盖前者
        seen[model.id] = model
    return list(seen.values())


def _normalize_keywords(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        return [text] if text else []
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    return [str(raw)]


def _normalize_steps(raw: Any) -> List[CaseStep]:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        return [CaseStep(no=None, action=text, expected=None, keyword=None, note=None)]
    if isinstance(raw, list):
        steps: List[CaseStep] = []
        for item in raw:
            if isinstance(item, dict):
                steps.append(CaseStep.from_dict(item))
        return steps
    return []
