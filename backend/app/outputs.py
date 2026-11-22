from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel

from .auth import Actor
from .schemas import DraftOutput, KnowledgeItemInput, QueryInput

T = TypeVar("T")
Scope = Literal["own", "department", "all"]
QueryStatus = Literal["ok", "denied", "invalid", "error"]
Status = Literal["draft", "published", "archived"]

class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int

class LoginResult(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    user: Actor

class AccessUser(BaseModel):
    id: int
    username: str
    name: str
    department: str
    roles: list[str]

class AccessRole(BaseModel):
    id: int
    code: str
    name: str
    grants: dict[str, Scope]

class AccessOverview(BaseModel):
    users: list[AccessUser]
    roles: list[AccessRole]

class AuditEntry(BaseModel):
    id: int
    user_id: int
    username: str
    action: str
    resource: str
    resource_id: int | None
    detail: dict[str, Any]
    created_at: str

class CatalogRow(BaseModel):
    id: int
    code: str
    name: str
    description: str

class Metric(CatalogRow):
    dataset_id: int
    unit: str

class Dimension(CatalogRow):
    dataset_id: int
    values: list[str] | None = None

class Asset(BaseModel):
    id: int
    filename: str
    mime: str
    size_bytes: int

class CsvPreview(BaseModel):
    headers: list[str]
    rows: list[list[str]]
    total_rows: int

class MetricValue(BaseModel):
    label: str
    value: int | float | None

class QueryComparison(BaseModel):
    start: str
    end: str
    rows: list[MetricValue]

class KnowledgePackRow(BaseModel):
    id: int
    dataset_id: int
    title: str
    description: str
    revision: int
    updated_at: str

class KnowledgePack(KnowledgePackRow):
    items: list[KnowledgeItemInput]

class KnowledgeSnapshot(BaseModel):
    id: int
    title: str
    revision: int
    items: list[KnowledgeItemInput]

class AnalysisContext(BaseModel):
    id: int
    dataset_id: int
    knowledge_pack_id: int | None
    title: str
    objective: str
    archived: bool
    updated_at: str
    pack_title: str | None

class QuerySnapshot(BaseModel):
    metric_name: str
    metric_note: str
    unit: str
    dimension_name: str
    dimension_code: str | None = None
    channel: str | None = None
    scope: Scope
    start: str
    end: str
    rows: list[MetricValue]
    knowledge: KnowledgeSnapshot | None = None
    comparison: QueryComparison | None = None

class QueryResult(QuerySnapshot):
    id: int

class QueryPlan(QueryInput):
    scope: Literal["own", "department"]
    notes: list[str]
    source: Literal["rules", "llm"]

class QueryRecord(BaseModel):
    id: int
    user_id: int
    department_id: int
    dataset_id: int
    metric: str
    dimension: str
    scope: Scope
    status: QueryStatus
    elapsed_ms: int
    row_count: int
    created_at: str

class QueryLog(QueryRecord):
    username: str
    dataset_name: str

class QueryDetail(QueryRecord):
    context_id: int | None = None
    filters: dict[str, Any]
    result: QuerySnapshot | None

class ReportRow(BaseModel):
    id: int
    title: str
    description: str
    status: Status
    owner_id: int
    owner_name: str
    current_version: int | None
    updated_at: str

class ReportSummary(BaseModel):
    total: int
    draft: int
    published: int
    archived: int

class ReportSnapshot(BaseModel):
    title: str
    description: str
    content: str
    dataset_id: int | None
    query_id: int | None
    asset_ids: list[int]
    assets: list[Asset]
    query: QuerySnapshot | None

class Report(ReportSnapshot):
    id: int
    owner_id: int
    department_id: int
    status: Status
    current_version: int | None
    created_at: str
    updated_at: str
    etag: str
    has_unpublished_changes: bool
    allowed: dict[str, bool]

class Version(ReportSnapshot):
    report_id: int
    number: int
    created_by: int
    created_at: str
    restored_from: int | None

class VersionEntry(BaseModel):
    number: int
    created_at: str
    restored_from: int | None
    created_by_name: str

class FeedbackEntry(BaseModel):
    id: int
    author_name: str
    body: str
    created_at: str

class PublishResult(BaseModel):
    report_id: int
    number: int
    status: Literal["published"]
    restored_from: int | None

class DiffItem(BaseModel):
    field: str
    before: str | int | list[int] | None
    after: str | int | list[int] | None

class DiffResult(BaseModel):
    base: int
    target: int
    changes: list[DiffItem]
    query_changes: list[DiffItem]
    content_changed: bool
    content_diff: list[str]

class GeneratedDraft(DraftOutput):
    mode: Literal["mock", "llm"]
    query_id: int
