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
import threading

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

# 配置控制台编码处理（解决Windows GBK编码问题）
import sys
import io
import os
if sys.platform == "win32":
    # 包装stdout/stderr为UTF-8编码
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 确保日志目录存在（相对于项目根目录）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log_file_path = os.path.join(project_root, logging_config["file"])
log_dir = os.path.dirname(log_file_path)
os.makedirs(log_dir, exist_ok=True)

# 配置日志格式
log_format = logging_config["format"]
formatter = logging.Formatter(log_format)

# 创建根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, logging_config["level"]))
root_logger.handlers.clear()

# 创建控制台处理器（Windows下使用UTF-8编码的stream）
if sys.platform == "win32":
    import io
    console_handler = logging.StreamHandler(stream=io.TextIOWrapper(
        sys.stdout.buffer, encoding='utf-8', errors='replace'
    ))
else:
    console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, logging_config["level"]))
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

# 创建文件处理器（强制UTF-8编码）
file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
file_handler.setLevel(getattr(logging, logging_config["level"]))
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

# 使用统一的API路由注册（延迟导入，避免过早加载模型）
from core.database import engine, Base, _upgrade_schema

# Create FastAPI app
app = FastAPI(
    title="SmartCut API",
    description="AI视频智能切片系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Create database tables
@app.on_event("startup")
async def startup_event():
    logger.info("启动SmartCut API服务...")
    # 不再导入模型，因为api_router已经导入了
    # 直接创建表
    Base.metadata.create_all(bind=engine)
    _upgrade_schema(engine)
    logger.info("数据库表创建完成")

    # 加载API密钥到环境变量
    api_key = get_api_key()
    if api_key:
        os.environ["DASHSCOPE_API_KEY"] = api_key
        logger.info("API密钥已加载到环境变量")
    else:
        logger.warning("未找到API密钥配置")

    # 启动后台线程预加载语音模型（不影响主线程启动）
    import time
    logger.info("启动后台线程预加载语音模型...")
    preload_thread = threading.Thread(
        target=background_preload_models,
        name="ASR-Preload-Thread",
        daemon=True  # 守护线程，主进程退出时自动结束
    )
    preload_thread.start()
    logger.info("[OK] 后台预加载已启动，服务已就绪（模型将在后台加载中）")

    # 启动WebSocket网关服务 - 已禁用，使用新的简化进度系统
    logger.info("WebSocket网关服务已禁用，使用新的简化进度系统")


def background_preload_models():
    """
    后台线程预加载语音识别模型
    
    特点：
    - 在独立线程中运行，不阻塞主线程
    - 主线程可立即启动服务（3秒）
    - 模型在后台加载（144秒），加载完成后自动可用
    - 首次使用时如果模型未加载完，会等待完成
    """
    from backend.utils.speech_recognizer import (
        _detect_compute_device,
        _FUNASR_MODEL_CACHE,
        SpeechRecognitionMethod,
        SpeechRecognizer
    )
    
    try:
        # 检测是否禁用预加载
        disable_all = os.environ.get("DISABLE_ASR_PRELOAD", "false").lower() == "true"
        disable_funasr = os.environ.get("DISABLE_FUNASR_PRELOAD", "false").lower() == "true"
        
        if disable_all or disable_funasr:
            logger.info("[INFO] 预加载已禁用，模型将在首次使用时加载")
            return
        
        # 检测计算设备
        device = _detect_compute_device()
        logger.info(f"[后台线程] 检测到计算设备: {device}")
        
        # 预加载 FunASR
        try:
            import time
            funasr_start = time.time()
            
            from funasr import AutoModel
            from backend.utils.speech_recognizer import (
                _mark_funasr_loading_start,
                _mark_funasr_loading_complete
            )
            
            # 标记加载开始
            _mark_funasr_loading_start()
            
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
                
                logger.info(f"[后台线程] 开始加载 FunASR 模型（量化: {use_quantize}）...")
                _FUNASR_MODEL_CACHE[cache_key] = AutoModel(**model_kwargs)
            
            # 标记加载完成
            _mark_funasr_loading_complete()
            
            funasr_elapsed = time.time() - funasr_start
            logger.info(f"[OK] [后台线程] FunASR模型预加载完成，耗时: {funasr_elapsed:.2f}秒")
            
        except Exception as e:
            logger.warning(f"[WARN] [后台线程] FunASR预加载失败: {e}")
            logger.info("[INFO] FunASR 将在首次使用时重新尝试加载")
            # 加载失败也标记完成，避免无限等待
            _mark_funasr_loading_complete()
        
        # 预加载 Whisper（作为备选）
        try:
            import whisper
            logger.info("[后台线程] 开始加载 Whisper 模型...")
            whisper.load_model("small")
            logger.info("[OK] [后台线程] Whisper模型预加载完成")
        except Exception as e:
            logger.warning(f"[WARN] [后台线程] Whisper预加载失败: {e}")
        
        logger.info("[后台线程] 所有语音模型预加载完成")
        
    except Exception as e:
        logger.error(f"[FAIL] [后台线程] 模型预加载异常: {e}")
        import traceback
        logger.debug(traceback.format_exc())


async def preload_speech_models():
    """
    异步预加载语音识别模型（保留原接口，内部改为线程）
    """
    import time
    logger.info("开始预加载语音识别模型...")
    
    # 检查是否禁用
    disable_all = os.environ.get("DISABLE_ASR_PRELOAD", "false").lower() == "true"
    disable_funasr = os.environ.get("DISABLE_FUNASR_PRELOAD", "false").lower() == "true"
    disable_whisper = os.environ.get("DISABLE_WHISPER_PRELOAD", "false").lower() == "true"
    
    if disable_all:
        logger.info("⚠️ 检测到 DISABLE_ASR_PRELOAD=true，跳过所有模型预加载")
        logger.info("💡 模型将在首次使用时自动加载（首次调用会稍慢）")
        return
    
    logger.info("开始预加载语音识别模型...")
    if disable_funasr:
        logger.info("💡 FunASR 预加载已禁用，将在首次使用时加载")
    if disable_whisper:
        logger.info("💡 Whisper 预加载已禁用，将在首次使用时加载")
    
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
        if not disable_funasr:
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
                    
                    logger.info(f"开始加载 FunASR 模型（量化: {use_quantize}）...")
                    _FUNASR_MODEL_CACHE[cache_key] = AutoModel(**model_kwargs)
                
                funasr_elapsed = time.time() - funasr_start
                logger.info(f"[OK] FunASR模型预加载完成，耗时: {funasr_elapsed:.2f}秒")
                
            except Exception as e:
                logger.warning(f"[WARN] FunASR预加载失败: {e}")
                logger.info("💡 FunASR 将在首次使用时重新尝试加载")
        
        # 预加载Whisper模型（回退引擎）
        if not disable_whisper:
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
                logger.info("💡 Whisper 将在首次使用时重新尝试加载")
        
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
    allow_origins=["*"],  # 允许所有来源，或配置特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 延迟导入API路由（避免过早加载模型）
@app.get("/")
async def root():
    """API根路径"""
    return {
        "name": "AutoClip API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}

@app.get("/api/v1/status")
async def get_status():
    """获取服务状态"""
    try:
        from backend.utils.speech_recognizer import _FUNASR_MODEL_CACHE
        from backend.utils.speech_recognizer import _WHISPER_MODEL_CACHE
        
        funasr_loaded = _FUNASR_MODEL_CACHE is not None and len(_FUNASR_MODEL_CACHE) > 0
        whisper_loaded = _WHISPER_MODEL_CACHE is not None and len(_WHISPER_MODEL_CACHE) > 0
        
        return {
            "service": "AutoClip API",
            "version": "1.0.0",
            "models": {
                "funasr": {
                    "loaded": funasr_loaded,
                    "count": len(_FUNASR_MODEL_CACHE) if _FUNASR_MODEL_CACHE else 0
                },
                "whisper": {
                    "loaded": whisper_loaded,
                    "count": len(_WHISPER_MODEL_CACHE) if _WHISPER_MODEL_CACHE else 0
                }
            },
            "preload": "background_thread"
        }
    except Exception as e:
        return {
            "service": "AutoClip API",
            "version": "1.0.0",
            "status": "healthy",
            "error": f"Model cache check failed: {str(e)}"
        }

# 延迟导入所有API路由
from backend.api.v1 import api_router as api_v1_router
app.include_router(api_v1_router, prefix="/api/v1")

# 配置静态文件服务（如果目录存在）
static_dir = Path(project_root) / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser(description="AutoClip API")
    parser.add_argument("--host", default="0.0.0.0", help="主机地址")
    parser.add_argument("--port", type=int, default=8090, help="端口")
    parser.add_argument("--reload", action="store_true", help="启用热重载")
    args = parser.parse_args()
    
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )
