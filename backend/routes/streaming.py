"""
AI Panel Studio — SSE 实时推送 + 发言路由
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from models import (
    SpeechNextRequest,
    SpeechNextResponse,
    SpeechListResponse,
    ConsensusListResponse,
    DivergenceListResponse,
)
from services.discussions import discussion_exists
from services.speeches import trigger_next_speech, list_speeches
from services.consensus import list_consensus, list_divergence
from sse_manager import sse_manager, sse_event_generator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/discussions/{discussion_id}", tags=["Streaming"])


async def _ensure_discussion(discussion_id: int):
    if not await discussion_exists(discussion_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "DISCUSSION_NOT_FOUND", "message": f"discussion_id={discussion_id} 对应的讨论不存在"},
        )


# ============================================================
# SSE 端点
# ============================================================

@router.get("/stream")
async def stream(discussion_id: int, after_sequence: int | None = Query(default=None)):
    """
    SSE 实时消息流。

    事件类型:
      - speech.chunk     : 发言流式 token
      - speech.complete  : 完整发言落库
      - consensus.update : 共识新增/更新
      - divergence.update: 分歧新增/更新
      - error            : 流内异常
      - heartbeat        : 15s 心跳
    """
    await _ensure_discussion(discussion_id)

    queue = await sse_manager.subscribe(discussion_id)

    # 如果请求了重连补偿（after_sequence），在连接建立后先补推遗漏的事件
    # 补偿通过 sse_manager.broadcast 完成（各方监听同一个 queue）
    if after_sequence is not None:
        # 在后台补推历史数据
        import asyncio
        asyncio.create_task(_replay_missed_events(discussion_id, after_sequence))

    return StreamingResponse(
        sse_event_generator(discussion_id, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


async def _replay_missed_events(discussion_id: int, after_sequence: int):
    """补推断线期间遗漏的发言和共识/分歧更新。"""
    try:
        speeches = await list_speeches(discussion_id, after_sequence=after_sequence, page=1, page_size=1000)
        for speech in speeches["items"]:
            await sse_manager.broadcast(discussion_id, "speech.complete", dict(speech))

        consensus = await list_consensus(discussion_id)
        for c in consensus["items"]:
            await sse_manager.broadcast(discussion_id, "consensus.update", dict(c))

        divergence = await list_divergence(discussion_id)
        for d in divergence["items"]:
            await sse_manager.broadcast(discussion_id, "divergence.update", dict(d))
    except Exception as e:
        logger.error(f"重连补偿失败 discussion={discussion_id}: {e}")


# ============================================================
# 发言
# ============================================================

@router.get("/speeches", response_model=SpeechListResponse)
async def get_speeches(
    discussion_id: int,
    after_sequence: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    """查询历史发言。"""
    await _ensure_discussion(discussion_id)
    return await list_speeches(discussion_id, after_sequence=after_sequence, page=page, page_size=page_size)


@router.post("/speeches/next", response_model=SpeechNextResponse, status_code=202)
async def next_speech(discussion_id: int, data: SpeechNextRequest | None = None):
    """
    触发下一轮 AI 发言。

    发言结果通过 SSE (/stream) 异步推送，不在此响应中返回。
    """
    await _ensure_discussion(discussion_id)
    prompt_hint = data.prompt_hint if data else None

    try:
        result = await trigger_next_speech(discussion_id, prompt_hint=prompt_hint)
        return result
    except ValueError as e:
        msg = str(e)
        if "已结束" in msg:
            raise HTTPException(status_code=400, detail={"code": "DISCUSSION_COMPLETED", "message": msg})
        elif "已暂停" in msg:
            raise HTTPException(status_code=400, detail={"code": "DISCUSSION_PAUSED", "message": msg})
        elif "嘉宾" in msg or "专家" in msg:
            code = "NO_PANELISTS" if "生成嘉宾" in msg else "NO_EXPERTS"
            raise HTTPException(status_code=400, detail={"code": code, "message": msg})
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": msg})
    except RuntimeError as e:
        msg = str(e)
        if "生成中" in msg:
            raise HTTPException(status_code=409, detail={"code": "SPEECH_IN_PROGRESS", "message": msg})
        raise HTTPException(status_code=502, detail={"code": "AI_SERVICE_UNAVAILABLE", "message": msg})


# ============================================================
# 共识 & 分歧
# ============================================================

@router.get("/consensus", response_model=ConsensusListResponse)
async def get_consensus(discussion_id: int):
    """查询共识列表。"""
    await _ensure_discussion(discussion_id)
    return await list_consensus(discussion_id)


@router.get("/divergence", response_model=DivergenceListResponse)
async def get_divergence(discussion_id: int):
    """查询分歧列表。"""
    await _ensure_discussion(discussion_id)
    return await list_divergence(discussion_id)
