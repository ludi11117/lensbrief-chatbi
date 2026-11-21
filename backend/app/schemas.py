from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class Login(Input):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)

class RoleUpdate(Input):
    roles: list[Literal["analyst", "manager", "admin"]] = Field(max_length=3)

class ReportInput(Input):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=16000)
    dataset_id: int | None = Field(default=None, gt=0)
    query_id: int | None = Field(default=None, gt=0)
    asset_ids: list[int] = Field(default_factory=list, max_length=12)

class QueryInput(Input):
    dataset_id: int = Field(gt=0)
    metric: str = Field(min_length=1, max_length=32)
    dimension: str = Field(min_length=1, max_length=32)
    start: date
    end: date
    scope: Literal["own", "department", "all"] | None = None
    context_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def valid_range(self):
        if self.end < self.start or (self.end - self.start).days > 365:
            raise ValueError("日期范围需正向且最多覆盖 366 天。")
        return self

class DraftInput(Input):
    query_id: int = Field(gt=0)
    goal: str = Field(default="", max_length=500)

class DraftOutput(Input):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(max_length=500)
    content: str = Field(min_length=1, max_length=16000)

class KnowledgeItemInput(Input):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=800)
    metric_id: int | None = Field(default=None, gt=0)

class KnowledgePackInput(Input):
    dataset_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    items: list[KnowledgeItemInput] = Field(min_length=1, max_length=8)

class ContextInput(Input):
    dataset_id: int = Field(gt=0)
    knowledge_pack_id: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=120)
    objective: str = Field(default="", max_length=500)
    archived: bool = False
