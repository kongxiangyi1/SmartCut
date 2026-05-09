"""
测试API密钥
"""

from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends

from pydantic import BaseModel

import os

import json

from pathlib import Path


router = APIRouter()


class SettingsRequest(BaseModel):

    """设置请求模型"""

    # 多提供商支持

    llm_provider: Optional[str] = None

    dashscope_api_key: Optional[str] = None

    openai_api_key: Optional[str] = None

    gemini_api_key: Optional[str] = None

    siliconflow_api_key: Optional[str] = None

    model_name: Optional[str] = None

    chunk_size: Optional[int] = None

    min_score_threshold: Optional[float] = None

    max_clips_per_collection: Optional[int] = None


class ApiKeyTestRequest(BaseModel):

    """API密钥测试请求"""

    provider: str

    api_key: str

    model_name: str


class ApiKeyTestResponse(BaseModel):

    """API密钥测试响应"""

    success: bool

    error: Optional[str] = None


def get_settings_file_path() -> Path:

    """获取设置文件路径"""

    from backend.core.path_utils import get_settings_file_path as get_settings_path

    return get_settings_path()


def load_settings() -> Dict[str, Any]:

    """加载设置"""

    settings_file = get_settings_file_path()

    default_settings = {

        "llm_provider": "dashscope",

        "dashscope_api_key": "",

        "openai_api_key": "",

        "gemini_api_key": "",

        "siliconflow_api_key": "",

        "zhipu_api_key": "",

        "tencent_api_key": "",

        "model_name": "qwen-plus",

        "chunk_size": 5000,

        "min_score_threshold": 0.7,

        "max_clips_per_collection": 5

    }

    if settings_file.exists():

        try:

            with open(settings_file, 'r', encoding='utf-8') as f:

                saved_settings = json.load(f)

                default_settings.update(saved_settings)

        except Exception as e:

            print(f"加载设置文件失败: {e}")

    return default_settings


def save_settings(settings: Dict[str, Any]):

    """保存设置"""

    settings_file = get_settings_file_path()

    settings_file.parent.mkdir(parents=True, exist_ok=True)

    with open(settings_file, 'w', encoding='utf-8') as f:

        json.dump(settings, f, ensure_ascii=False, indent=2)


@router.get("/")
async def get_settings():
    """获取当前设置"""
    return load_settings()


@router.post("/")
async def update_settings(request: SettingsRequest):
    """更新设置"""
    settings = load_settings()
    
    # 更新设置
    if request.llm_provider is not None:
        settings["llm_provider"] = request.llm_provider
    if request.dashscope_api_key is not None:
        settings["dashscope_api_key"] = request.dashscope_api_key
    if request.openai_api_key is not None:
        settings["openai_api_key"] = request.openai_api_key
    if request.gemini_api_key is not None:
        settings["gemini_api_key"] = request.gemini_api_key
    if request.siliconflow_api_key is not None:
        settings["siliconflow_api_key"] = request.siliconflow_api_key
    if request.model_name is not None:
        settings["model_name"] = request.model_name
    if request.chunk_size is not None:
        settings["chunk_size"] = request.chunk_size
    if request.min_score_threshold is not None:
        settings["min_score_threshold"] = request.min_score_threshold
    if request.max_clips_per_collection is not None:
        settings["max_clips_per_collection"] = request.max_clips_per_collection
    
    save_settings(settings)
    return {"success": True, "message": "设置已更新"}


@router.post("/test-api-key")
async def test_api_key(request: ApiKeyTestRequest) -> ApiKeyTestResponse:
    """测试API密钥"""
    try:
        # 导入LLM管理
        from backend.core.llm_manager import get_llm_manager
        from backend.core.llm_providers import ProviderType
        
        # 调试：打印接收到的请求数据
        print(f"DEBUG - 接收到的请求数据:")
        print(f"  provider: '{request.provider}'")
        print(f"  provider类型: {type(request.provider)}")
        print(f"  api_key: '{request.api_key[:10]}...'")
        print(f"  model_name: '{request.model_name}'")
        
        # 调试：打印所有可用的 ProviderType 枚举值
        print(f"DEBUG - 可用的 ProviderType 枚举值:")
        for pt in ProviderType:
            print(f"  - {pt.name} = '{pt.value}'")
        
        # 验证提供商类
        try:
            provider_type = ProviderType(request.provider)
            print(f"DEBUG - 转换成功: {provider_type}")
        except ValueError as e:
            print(f"DEBUG - 转换失败: {e}")
            return ApiKeyTestResponse(success=False, error=f"不支持的提供商类型: {request.provider}")
        
        # 测试连接
        llm_manager = get_llm_manager()
        success = llm_manager.test_provider_connection(provider_type, request.api_key, request.model_name)
        
        if success:
            return ApiKeyTestResponse(success=True)
        else:
            return ApiKeyTestResponse(success=False, error="API连接测试失败")
                
    except Exception as e:
        print(f"DEBUG - 异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return ApiKeyTestResponse(success=False, error=str(e))


@router.get("/available-models")
async def get_available_models():
    """获取所有可用模型"""
    try:
        from backend.core.llm_manager import get_llm_manager
        llm_manager = get_llm_manager()
        return llm_manager.get_all_available_models()
    except Exception as e:
        return {"error": str(e)}


@router.get("/current-provider")
async def get_current_provider():
    """获取当前提供商信息"""
    try:
        from backend.core.llm_manager import get_llm_manager
        llm_manager = get_llm_manager()
        return llm_manager.get_current_provider_info()
    except Exception as e:
        return {"error": str(e)}


@router.get("/speech-recognition-methods")
async def get_speech_recognition_methods():
    """获取所有可用的语音识别方法"""
    try:
        from backend.utils.speech_recognition import get_available_recognition_methods
        methods = get_available_recognition_methods()
        return methods
    except Exception as e:
        print(f"获取语音识别方法失败: {e}")
        return {
            "funasr": {
                "name": "FunASR (本地)",
                "description": "使用阿里达摩院的FunASR进行本地语音识别",
                "requires_api_key": False,
                "requires_network": False,
                "available": True,
                "models": ["base", "small", "medium", "large"]
            },
            "whisper_local": {
                "name": "Whisper (本地)",
                "description": "使用OpenAI的Whisper进行本地语音识别",
                "requires_api_key": False,
                "requires_network": False,
                "available": True,
                "models": ["tiny", "base", "small", "medium", "large"]
            },
            "bcut_asr": {
                "name": "BCUT ASR",
                "description": "使用字节跳动BCUT进行语音识别",
                "requires_api_key": False,
                "requires_network": True,
                "available": False,
                "models": []
            },
            "openai_api": {
                "name": "OpenAI API",
                "description": "使用OpenAI API进行语音识别",
                "requires_api_key": True,
                "requires_network": True,
                "available": True,
                "models": ["whisper-1"]
            },
            "azure_speech": {
                "name": "Azure Speech",
                "description": "使用Azure语音服务进行语音识别",
                "requires_api_key": True,
                "requires_network": True,
                "available": False,
                "models": []
            },
            "google_speech": {
                "name": "Google Speech",
                "description": "使用Google语音服务进行语音识别",
                "requires_api_key": True,
                "requires_network": True,
                "available": False,
                "models": []
            },
            "aliyun_speech": {
                "name": "阿里云语音",
                "description": "使用阿里云语音服务进行语音识别",
                "requires_api_key": True,
                "requires_network": True,
                "available": False,
                "models": []
            }
        }