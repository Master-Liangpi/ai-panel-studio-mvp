"""
AI Panel Studio — 总结路由
"""

import logging
from fastapi import APIRouter, HTTPException
from models import SummaryResponse
from services.discussions import discussion_exists
from services.summaries import get_summary, generate_summary_for_discussion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/discussions/{discussion_id}/summary", tags=["Summary"])


async def _ensure_discussion(discussion_id: int):
    if not await discussion_exists(discussion_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "DISCUSSION_NOT_FOUND", "message": f"discussion_id={discussion_id} 对应的讨论不存在"},
        )


@router.get("", response_model=SummaryResponse)
async def get(discussion_id: int):
    """查询已有总结。"""
    await _ensure_discussion(discussion_id)
    result = await get_summary(discussion_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail={"code": "SUMMARY_NOT_FOUND", "message": "该讨论尚未生成总结，请先调用 POST 生成"},
        )
    return result


@router.post("", response_model=SummaryResponse)
async def generate(discussion_id: int):
    """生成收尾总结（讨论状态自动变更为 completed）。"""
    await _ensure_discussion(discussion_id)
    try:
        result = await generate_summary_for_discussion(discussion_id)
        return result
    except ValueError as e:
        msg = str(e)
        if "发言" in msg or "尚无" in msg:
            raise HTTPException(status_code=400, detail={"code": "NO_SPEECHES", "message": msg})
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": msg})
    except Exception as e:
        logger.error(f"生成总结失败: {e}")
        raise HTTPException(
            status_code=502,
            detail={"code": "AI_SERVICE_UNAVAILABLE", "message": "DeepSeek 服务暂时不可用，请稍后重试"},
        )
