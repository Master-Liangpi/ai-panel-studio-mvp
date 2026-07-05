"""
AI Panel Studio — 讨论会话路由
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from models import (
    DiscussionCreateRequest,
    DiscussionUpdateRequest,
    DiscussionResponse,
    DiscussionListResponse,
    ErrorResponse,
)
from services.discussions import (
    create_discussion,
    get_discussion,
    list_discussions,
    update_discussion,
    delete_discussion,
    discussion_exists,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/discussions", tags=["Discussions"])


@router.post("", response_model=DiscussionResponse, status_code=201)
async def create(data: DiscussionCreateRequest):
    """新建讨论会话。"""
    try:
        result = await create_discussion(title=data.title, topic=data.topic)
        return result
    except Exception as e:
        logger.error(f"创建讨论失败: {e}")
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


@router.get("", response_model=DiscussionListResponse)
async def list_all(
    status: str | None = Query(default=None, pattern=r"^(active|paused|completed)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """查询讨论列表。"""
    try:
        result = await list_discussions(status=status, page=page, page_size=page_size)
        return result
    except Exception as e:
        logger.error(f"查询讨论列表失败: {e}")
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


@router.get("/{discussion_id}", response_model=DiscussionResponse)
async def get_one(discussion_id: int):
    """查询单场讨论详情。"""
    result = await get_discussion(discussion_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail={"code": "DISCUSSION_NOT_FOUND", "message": f"discussion_id={discussion_id} 对应的讨论不存在"},
        )
    return result


@router.patch("/{discussion_id}", response_model=DiscussionResponse)
async def update(discussion_id: int, data: DiscussionUpdateRequest):
    """更新讨论信息。"""
    if not await discussion_exists(discussion_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "DISCUSSION_NOT_FOUND", "message": f"discussion_id={discussion_id} 对应的讨论不存在"},
        )
    updates = data.model_dump(exclude_none=True)
    if not updates:
        return await get_discussion(discussion_id)
    try:
        result = await update_discussion(discussion_id, **updates)
        return result
    except Exception as e:
        logger.error(f"更新讨论失败: {e}")
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": str(e)})


@router.delete("/{discussion_id}", status_code=204)
async def delete(discussion_id: int):
    """删除讨论（级联删除）。"""
    deleted = await delete_discussion(discussion_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"code": "DISCUSSION_NOT_FOUND", "message": f"discussion_id={discussion_id} 对应的讨论不存在"},
        )
    return None
