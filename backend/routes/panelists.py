"""
AI Panel Studio — 嘉宾路由
"""

import logging
from fastapi import APIRouter, HTTPException
from models import (
    PanelistGenerateRequest,
    PanelistCreateRequest,
    PanelistUpdateRequest,
    PanelistResponse,
    PanelistListResponse,
)
from services.discussions import discussion_exists
from services.panelists import (
    generate_panelists_for_discussion,
    list_panelists,
    add_panelist,
    update_panelist,
    delete_panelist,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/discussions/{discussion_id}/panelists", tags=["Panelists"])


async def _ensure_discussion(discussion_id: int):
    """确保讨论存在，否则抛 404。"""
    if not await discussion_exists(discussion_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "DISCUSSION_NOT_FOUND", "message": f"discussion_id={discussion_id} 对应的讨论不存在"},
        )


@router.post("/generate", response_model=PanelistListResponse, status_code=201)
async def generate(discussion_id: int, data: PanelistGenerateRequest):
    """AI 生成嘉宾阵容。"""
    await _ensure_discussion(discussion_id)
    try:
        result = await generate_panelists_for_discussion(
            discussion_id, count=data.count, topic_override=data.topic_override
        )
        return result
    except ValueError as e:
        msg = str(e)
        if "人数" in msg or "1~" in msg:
            raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": msg})
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": msg})
    except RuntimeError as e:
        logger.error(f"生成嘉宾失败: {e}")
        raise HTTPException(
            status_code=502,
            detail={"code": "AI_SERVICE_UNAVAILABLE", "message": "DeepSeek 服务暂时不可用，请稍后重试"},
        )


@router.get("", response_model=PanelistListResponse)
async def list_all(discussion_id: int):
    """查询嘉宾列表。"""
    await _ensure_discussion(discussion_id)
    return await list_panelists(discussion_id)


@router.post("", response_model=PanelistResponse, status_code=201)
async def add(discussion_id: int, data: PanelistCreateRequest):
    """手动添加嘉宾。"""
    await _ensure_discussion(discussion_id)
    try:
        result = await add_panelist(discussion_id, **data.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "BUSINESS_CONFLICT", "message": str(e)})


@router.patch("/{panelist_id}", response_model=PanelistResponse)
async def update(discussion_id: int, panelist_id: int, data: PanelistUpdateRequest):
    """修改嘉宾信息。"""
    await _ensure_discussion(discussion_id)
    updates = data.model_dump(exclude_none=True)
    result = await update_panelist(discussion_id, panelist_id, **updates)
    if not result:
        raise HTTPException(
            status_code=404,
            detail={"code": "PANELIST_NOT_FOUND", "message": f"discussion_id={discussion_id} 中不存在 panelist_id={panelist_id}"},
        )
    return result


@router.delete("/{panelist_id}", status_code=204)
async def delete(discussion_id: int, panelist_id: int):
    """移除嘉宾。"""
    await _ensure_discussion(discussion_id)
    deleted = await delete_panelist(discussion_id, panelist_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"code": "PANELIST_NOT_FOUND", "message": f"discussion_id={discussion_id} 中不存在 panelist_id={panelist_id}"},
        )
    return None
