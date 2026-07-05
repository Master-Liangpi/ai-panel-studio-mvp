"""
AI Panel Studio — SSE 连接管理器
按 discussion_id 隔离消息通道，多客户端订阅互不干扰。
"""

import asyncio
import json
import logging
from config import SSE_HEARTBEAT_INTERVAL

logger = logging.getLogger(__name__)


class SSEManager:
    """
    管理所有讨论的 SSE 客户端连接。

    每个讨论维护一个客户端队列列表。
    broadcast() 向该讨论的所有订阅者推送事件。
    客户端断连时自动清理队列。
    """

    def __init__(self):
        # discussion_id → list[asyncio.Queue]
        self._queues: dict[int, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, discussion_id: int) -> asyncio.Queue:
        """订阅某个讨论的 SSE 事件流，返回专属队列。"""
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            if discussion_id not in self._queues:
                self._queues[discussion_id] = []
            self._queues[discussion_id].append(queue)
        logger.info(f"SSE client subscribed to discussion {discussion_id}, "
                     f"total clients: {len(self._queues[discussion_id])}")
        return queue

    async def unsubscribe(self, discussion_id: int, queue: asyncio.Queue) -> None:
        """取消订阅，清理队列。"""
        async with self._lock:
            if discussion_id in self._queues:
                try:
                    self._queues[discussion_id].remove(queue)
                except ValueError:
                    pass
                if not self._queues[discussion_id]:
                    del self._queues[discussion_id]
        logger.info(f"SSE client unsubscribed from discussion {discussion_id}")

    async def broadcast(self, discussion_id: int, event: str, data: dict | None = None) -> None:
        """
        向订阅了指定讨论的所有客户端推送事件。

        Args:
            discussion_id: 讨论 ID
            event: SSE 事件类型 (speech.chunk, speech.complete, consensus.update, divergence.update, error, heartbeat)
            data: 事件数据 dict，为 None 时推送空对象 {}
        """
        payload = data or {}
        async with self._lock:
            queues = list(self._queues.get(discussion_id, []))
        dead_queues = []
        for queue in queues:
            try:
                await queue.put((event, payload))
            except Exception:
                dead_queues.append(queue)
        # 清理已失效的队列
        if dead_queues:
            async with self._lock:
                for q in dead_queues:
                    try:
                        self._queues.get(discussion_id, []).remove(q)  # type: ignore[arg-type]
                    except (ValueError, KeyError):
                        pass

    async def broadcast_error(self, discussion_id: int, code: str, message: str) -> None:
        """推送错误事件。"""
        await self.broadcast(discussion_id, "error", {"code": code, "message": message})

    def client_count(self, discussion_id: int) -> int:
        """返回某个讨论的当前订阅者数量。"""
        return len(self._queues.get(discussion_id, []))


# 全局单例
sse_manager = SSEManager()


# ============================================================
# SSE 事件流生成器（FastAPI StreamingResponse 使用）
# ============================================================

async def sse_event_generator(discussion_id: int, queue: asyncio.Queue):
    """
    SSE 事件流异步生成器。
    从队列中读取事件并格式化为 SSE 协议文本。
    自动发送心跳，客户端断连时退出。
    """
    heartbeat_interval = SSE_HEARTBEAT_INTERVAL
    try:
        while True:
            try:
                # 等待事件，超时则发送心跳
                event, data = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
                yield _format_sse(event, data)
            except asyncio.TimeoutError:
                # 心跳
                yield _format_sse("heartbeat", {})
    except asyncio.CancelledError:
        pass
    finally:
        await sse_manager.unsubscribe(discussion_id, queue)


def _format_sse(event: str, data: dict) -> str:
    """
    格式化为 SSE 协议文本。

    SSE 格式:
        event: <event_name>\n
        data: <json_payload>\n
        \n
    """
    data_json = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {data_json}\n\n"
