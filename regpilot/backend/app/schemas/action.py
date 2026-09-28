"""合规动作相关 schema（ActionItem 用于 LLM 输出校验，ActionOut 见 analysis.py 中的定义）。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ActionOut 统一定义在 analysis.py 中以避免重复，这里做一次转引，保持 schemas 包导出路径稳定
from app.schemas.analysis import ActionOut  # noqa: F401

_DEPARTMENTS = Literal[
    "Legal", "Product", "Engineering", "Security", "Operations", "Supply Chain", "Management"
]


class ActionItem(BaseModel):
    """LLM 输出的整改动作条目（action 节点校验用）。"""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., min_length=1)
    priority: Literal["low", "medium", "high"] = "medium"
    department: _DEPARTMENTS = "Legal"
    description: str = ""
    evidence: dict | None = None
