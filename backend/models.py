"""
AI Panel Studio — Pydantic 数据模型
请求体 / 响应体 / SSE 事件 Payload 的严格类型定义。
与 api-contract.yaml OpenAPI 规范一一对应。
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import re


# ============================================================
# 讨论
# ============================================================

class DiscussionCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="讨论标题")
    topic: str = Field(default="", max_length=2000, description="议题简述")


class DiscussionUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    topic: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[str] = Field(default=None, pattern=r"^(active|paused|completed)$")


class DiscussionResponse(BaseModel):
    id: int
    title: str
    topic: str = ""
    status: str
    panelist_count: int = 0
    speech_count: int = 0
    created_at: str
    updated_at: str


class DiscussionListResponse(BaseModel):
    items: list[DiscussionResponse]
    total: int


# ============================================================
# 嘉宾
# ============================================================

class PanelistGenerateRequest(BaseModel):
    count: int = Field(..., ge=1, le=10, description="生成嘉宾人数（含主持人）")
    topic_override: Optional[str] = Field(default=None, max_length=2000, description="临时覆盖议题")


class PanelistCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    title: str = Field(default="", max_length=200)
    stance: str = Field(default="", max_length=1000)
    color: str = Field(default="#3388FF", pattern=r"^#[0-9A-Fa-f]{6}$")
    role: str = Field(..., pattern=r"^(host|expert)$")
    avatar_url: Optional[str] = None

    @field_validator("color")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("颜色必须是合法的 Hex 格式，如 #E74C3C")
        return v.upper()


class PanelistUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    title: Optional[str] = Field(default=None, max_length=200)
    stance: Optional[str] = Field(default=None, max_length=1000)
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    role: Optional[str] = Field(default=None, pattern=r"^(host|expert)$")
    avatar_url: Optional[str] = None


class PanelistResponse(BaseModel):
    id: int
    discussion_id: int
    name: str
    title: str = ""
    stance: str = ""
    color: str
    role: str
    avatar_url: Optional[str] = None
    created_at: str


class PanelistListResponse(BaseModel):
    items: list[PanelistResponse]
    host: Optional[PanelistResponse] = None
    experts: list[PanelistResponse] = []


# ============================================================
# 发言
# ============================================================

class SpeechNextRequest(BaseModel):
    prompt_hint: Optional[str] = Field(default=None, max_length=2000, description="发言引导提示")


class SpeechResponse(BaseModel):
    id: int
    discussion_id: int
    panelist_id: int
    panelist_name: str = ""
    panelist_color: str = "#3388FF"
    content: str
    sequence_num: int
    created_at: str


class SpeechListResponse(BaseModel):
    items: list[SpeechResponse]
    total: int


class SpeechNextResponse(BaseModel):
    accepted: bool = True
    message: str = "发言生成已启动，请通过 SSE 流获取内容"
    estimated_seconds: float = 3.5


# ============================================================
# 共识
# ============================================================

class ConsensusPointResponse(BaseModel):
    id: int
    discussion_id: int
    topic: str
    content: str
    latest_speech_id: Optional[int] = None
    created_at: str
    updated_at: str


class ConsensusListResponse(BaseModel):
    items: list[ConsensusPointResponse]
    total: int


# ============================================================
# 分歧
# ============================================================

class DivergencePointResponse(BaseModel):
    id: int
    discussion_id: int
    topic: str
    content: str
    sides: str = ""
    latest_speech_id: Optional[int] = None
    created_at: str
    updated_at: str


class DivergenceListResponse(BaseModel):
    items: list[DivergencePointResponse]
    total: int


# ============================================================
# 总结
# ============================================================

class SummaryResponse(BaseModel):
    discussion_id: int
    content: str
    generated_at: str


# ============================================================
# SSE 事件 Payload
# ============================================================

class SSEChunkPayload(BaseModel):
    sequence_num: int
    panelist_id: int
    delta: str


class SSEErrorPayload(BaseModel):
    code: str
    message: str


# ============================================================
# 通用错误
# ============================================================

class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: str = ""
