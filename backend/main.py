"""
AI Panel Studio — FastAPI 应用入口
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
启动: uvicorn main:app --reload
文档: http://localhost:8000/docs (Swagger)
      http://localhost:8000/redoc (ReDoc)
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import LOG_LEVEL, SERVER_HOST, SERVER_PORT, validate_config
from database import init_database

# ---- 日志配置 ----
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ai_panel_studio")


# ---- 应用生命周期 ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的初始化与清理。"""
    # 启动
    logger.info("=" * 60)
    logger.info("AI Panel Studio 后端启动中...")

    # 校验配置
    errors = validate_config()
    if errors:
        for err in errors:
            logger.warning(f"⚠ 配置警告: {err}")

    # 初始化数据库
    try:
        await init_database()
        logger.info("✓ 数据库初始化完成")
    except Exception as e:
        logger.error(f"✗ 数据库初始化失败: {e}")
        raise

    logger.info(f"✓ API 文档: http://{SERVER_HOST}:{SERVER_PORT}/docs")
    logger.info("=" * 60)

    yield

    # 关闭
    logger.info("AI Panel Studio 后端关闭")


# ---- 创建应用 ----
app = FastAPI(
    title="AI Panel Studio API",
    description="AI 圆桌演播厅后端接口。DeepSeek 密钥仅存于后端环境变量，前端不接触。",
    version="1.0.0",
    lifespan=lifespan,
)

# ---- CORS（允许前端跨域访问） ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- 全局异常处理 ----
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """兜底异常处理，避免后端内部细节泄露到前端。"""
    logger.error(f"未处理异常 {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误，请稍后重试",
            # detail 仅在开发环境返回
            "detail": str(exc) if LOG_LEVEL.lower() == "debug" else "",
        },
    )


# ---- 注册路由 ----
from routes.discussions import router as discussions_router
from routes.panelists import router as panelists_router
from routes.streaming import router as streaming_router
from routes.summaries import router as summaries_router

app.include_router(discussions_router, prefix="/api/v1")
app.include_router(panelists_router, prefix="/api/v1")
app.include_router(streaming_router, prefix="/api/v1")
app.include_router(summaries_router, prefix="/api/v1")


# ---- 健康检查 ----
@app.get("/api/v1/health")
async def health_check():
    """健康检查端点。"""
    return {"status": "ok", "service": "AI Panel Studio", "version": "1.0.0"}


# ---- 直接运行入口 ----
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,
        log_level=LOG_LEVEL,
    )
