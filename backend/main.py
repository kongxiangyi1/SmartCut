"""FastAPI应用入口点"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import sys
import os

# 消除 Hugging Face 和 transformers 警告
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# 确保项目根目录在路径中（支持绝对导入）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
# 确保backend目录在路径中
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 导入配置管理
from core.config import settings, get_logging_config, get_api_key

# 配置日志
logging_config = get_logging_config()
logging.basicConfig(
    level=getattr(logging, logging_config["level"]),
    format=logging_config["format"],
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
        logging.FileHandler(logging_config["file"])  # 输出到文件
    ]
)

logger = logging.getLogger(__name__)

# 使用统一的API路由注册（延迟导入，避免过早加载模型）
from core.database import engine, Base

# Create FastAPI app
app = FastAPI(
    title="AutoClip API",
    description="AI视频切片处理API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Create database tables
@app.on_event("startup")
async def startup_event():
    logger.info("启动AutoClip API服务...")
    # 不再导入模型，因为api_router已经导入了
    # 直接创建表
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表创建完成")

    # 加载API密钥到环境变量
    api_key = get_api_key()
    if api_key:
        os.environ["DASHSCOPE_API_KEY"] = api_key
        logger.info("API密钥已加载到环境变量")
    else:
        logger.warning("未找到API密钥配置")

    # 启动时预加载语音识别模型（避免首次调用延迟）
    import asyncio
    asyncio.create_task(preload_speech_models())
    logger.info("语音识别模型预加载已在后台启动")

    # 启动WebSocket网关服务 - 已禁用，使用新的简化进度系统
    logger.info("WebSocket网关服务已禁用，使用新的简化进度系统")

async def preload_speech_models():
    """
    预加载语音识别模型
    在应用启动时提前加载模型，避免首次调用时的延迟
    
    加载顺序：
    1. FunASR（默认引擎）
    2. Whisper（回退引擎）
    """
    logger.info("开始预加载语音识别模型...")
    
    try:
        # 导入语音识别模块
        from backend.utils.speech_recognizer import (
            _detect_compute_device,
            _FUNASR_MODEL_CACHE,
            SpeechRecognitionMethod,
            SpeechRecognizer
        )
        
        # 检测计算设备
        device = _detect_compute_device()
        logger.info(f"检测到计算设备: {device}")
        
        # 预加载FunASR模型（默认引擎）
        try:
            import time
            funasr_start = time.time()
            
            from funasr import AutoModel
            
            use_quantize = os.environ.get("FUNASR_QUANTIZE", "true").lower() == "true"
            cache_key = f"{device}_{'quantized' if use_quantize else 'full'}"
            
            if cache_key not in _FUNASR_MODEL_CACHE:
                model_kwargs = {
                    "model": "paraformer-zh",
                    "vad_model": "fsmn-vad",
                    "punc_model": "ct-punc",
                    "device": device,
                    "disable_update": True,
                    "cache_dir": str(Path.home() / ".cache" / "funasr"),
                }
                
                if use_quantize:
                    model_kwargs.update({
                        "quantize": True,
                        "int8": True,
                    })
                
                _FUNASR_MODEL_CACHE[cache_key] = AutoModel(**model_kwargs)
            
            funasr_elapsed = time.time() - funasr_start
            logger.info(f"[OK] FunASR模型预加载完成，耗时: {funasr_elapsed:.2f}秒")
            
        except Exception as e:
            logger.warning(f"[WARN] FunASR预加载失败: {e}")
        
        # 预加载Whisper模型（回退引擎）
        try:
            import time
            whisper_start = time.time()
            
            import whisper
            # 预加载small模型（平衡速度和准确率）
            whisper.load_model("small")
            
            whisper_elapsed = time.time() - whisper_start
            logger.info(f"[OK] Whisper模型预加载完成，耗时: {whisper_elapsed:.2f}秒")
            
        except Exception as e:
            logger.warning(f"[WARN] Whisper预加载失败: {e}")
        
        logger.info("语音识别模型预加载完成")
        
    except Exception as e:
        logger.error(f"[FAIL] 语音识别模型预加载异常: {e}")
        # 预加载失败不影响服务启动，首次调用时会自动加载

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("正在关闭AutoClip API服务...")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include unified API routes（延迟导入，避免过早加载模型）
from api.v1 import api_router
app.include_router(api_router, prefix="/api/v1")

# 静态文件服务配置
frontend_dist_dir = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist_dir.exists() and (frontend_dist_dir / "static").exists():
    app.mount("/static", StaticFiles(directory=frontend_dist_dir / "static"), name="static")

    # SPA路由回退处理
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        index_path = frontend_dist_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
else:
    logger.info("前端dist目录不存在，跳过静态文件服务配置")

# 添加独立的video-categories端点
@app.get("/api/v1/video-categories")
async def get_video_categories():
    """获取视频分类配置."""
    return {
        "categories": [
            {
                "value": "default",
                "name": "默认",
                "description": "通用视频内容处理",
                "icon": "[VIDEO]",
                "color": "#4facfe"
            },
            {
                "value": "knowledge",
                "name": "知识科普",
                "description": "科学、技术、历史、文化等知识类内容",
                "icon": "[DOC]",
                "color": "#52c41a"
            },
            {
                "value": "entertainment",
                "name": "娱乐",
                "description": "游戏、音乐、电影等娱乐内容",
                "icon": "🎮",
                "color": "#722ed1"
            },
            {
                "value": "business",
                "name": "商业",
                "description": "商业、创业、投资等商业内容",
                "icon": "💼",
                "color": "#fa8c16"
            },
            {
                "value": "experience",
                "name": "经验分享",
                "description": "个人经历、生活感悟等经验内容",
                "icon": "🌟",
                "color": "#eb2f96"
            },
            {
                "value": "opinion",
                "name": "观点评论",
                "description": "时事评论、观点分析等评论内容",
                "icon": "💭",
                "color": "#13c2c2"
            },
            {
                "value": "speech",
                "name": "演讲",
                "description": "公开演讲、讲座等演讲内容",
                "icon": "🎤",
                "color": "#f5222d"
            }
        ]
    }

# 导入统一错误处理中间件
from core.error_middleware import global_exception_handler

# 注册全局异常处理器
app.add_exception_handler(Exception, global_exception_handler)

if __name__ == "__main__":
    import uvicorn

    # 默认端口 - 固定为8090
    port = 8090

    # 检查命令行参数
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                try:
                    port = int(sys.argv[i + 1])
                except ValueError:
                    logger.error(f"无效的端口号: {sys.argv[i + 1]}")
                    port = 8000

    logger.info(f"启动服务器，端口: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)