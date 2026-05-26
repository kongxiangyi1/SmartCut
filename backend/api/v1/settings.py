"""
设置相关API - 安全版本
实现加密存储、完整性校验、密钥管理等安全功能
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException

from backend.models.enums import (
    LLMConfigStatus,
    ProcessMode,
    LLMStatusInfo,
    ModeSelectionInfo,
)

router = APIRouter(tags=["settings"])
logger = logging.getLogger(__name__)


# ========================================
# 安全配置辅助函数
# ========================================

def _get_secure_manager():
    """延迟导入安全配置管理器"""
    from backend.services.secure_config_manager import secure_config_manager
    return secure_config_manager


def _get_default_settings():
    """获取默认配置"""
    from backend.core.config import settings
    return settings


# ========================================
# 新API端点（LLM降级相关）
# ========================================

@router.get("/llm-config-status", response_model=LLMStatusInfo)
def get_llm_config_status():
    """获取LLM配置状态"""
    try:
        settings = _get_default_settings()
        secure_manager = _get_secure_manager()
        
        # 获取保存的提供商配置
        llm_provider = secure_manager.get('llm_provider', 'dashscope')
        
        # 检查是否有有效的API Key
        provider_key_map = {
            'dashscope': 'api_dashscope_api_key',
            'openai': 'api_openai_api_key',
            'gemini': 'api_gemini_api_key',
            'siliconflow': 'api_siliconflow_api_key',
            'zhipu': 'api_zhipu_api_key',
            'tencent': 'api_tencent_api_key',
            'ollama': 'api_ollama_api_key',
            'lmstudio': 'api_lmstudio_api_key',
        }
        
        key_name = provider_key_map.get(llm_provider, 'api_dashscope_api_key')
        has_key = secure_manager.has_sensitive_value(key_name)
        
        if not has_key and llm_provider == 'dashscope':
            has_key = bool(settings.api_dashscope_api_key)
        
        if not has_key:
            return LLMStatusInfo(
                status=LLMConfigStatus.NOT_CONFIGURED,
                message="AI模型未配置，请先添加API Key",
                available_modes=[ProcessMode.SUBTITLE_ORGANIZED.value, ProcessMode.QUICK_PREVIEW.value]
            )
        
        model_name = secure_manager.get('model_name', settings.api_model_name)
        
        return LLMStatusInfo(
            status=LLMConfigStatus.CONFIGURED,
            message="AI模型配置正常",
            provider=llm_provider,
            model=model_name,
            available_modes=[m.value for m in ProcessMode]
        )
            
    except Exception as e:
        logger.error(f"获取LLM状态失败: {e}", exc_info=True)
        return LLMStatusInfo(
            status=LLMConfigStatus.SERVICE_UNAVAILABLE,
            message="检查配置时出错"
        )


@router.get("/process-modes", response_model=List[dict])
def get_process_modes():
    """获取所有处理模式信息"""
    mode_infos = ModeSelectionInfo.get_all_modes_info()
    return [m.to_dict() for m in mode_infos]


@router.get("/process-modes/recommended")
def get_recommended_mode():
    """获取推荐的处理模式"""
    from backend.pipeline.director import LLMStateMonitor
    monitor = LLMStateMonitor()
    llm_status = monitor.get_current_status()
    
    if llm_status.is_available:
        recommended_mode = ProcessMode.AI_SMART
    else:
        recommended_mode = ProcessMode.SUBTITLE_ORGANIZED
    
    mode_infos = ModeSelectionInfo.get_all_modes_info()
    recommended_info = next((m for m in mode_infos if m.mode == recommended_mode), None)
    
    return {
        "recommended_mode": recommended_mode.value,
        "mode_info": recommended_info.to_dict() if recommended_info else None,
        "llm_available": llm_status.is_available,
        "llm_status": llm_status.to_dict()
    }


# ========================================
# 安全API端点 - 掩码显示敏感信息
# ========================================

@router.get("/secure")
def get_secure_settings():
    """
    获取安全的配置信息（API Key显示掩码）
    用于前端显示，不返回完整密钥
    """
    try:
        settings = _get_default_settings()
        secure_manager = _get_secure_manager()
        
        llm_provider = secure_manager.get('llm_provider', 'dashscope')
        model_name = secure_manager.get('model_name', settings.api_model_name)
        
        # 构建返回结果（所有敏感字段返回掩码）
        result = {
            "llm_provider": llm_provider,
            "model_name": model_name,
            "chunk_size": secure_manager.get('chunk_size', settings.processing_chunk_size),
            "min_score_threshold": secure_manager.get('min_score_threshold', settings.processing_min_score_threshold),
            "max_clips_per_collection": secure_manager.get('max_clips_per_collection', settings.processing_max_clips_per_collection),
            "speech_recognition_method": secure_manager.get('speech_recognition_method', 'funasr'),
            "speech_recognition_model": secure_manager.get('speech_recognition_model', 'base'),
            # 敏感字段返回掩码（同时返回两种格式）
            "api_dashscope_api_key": secure_manager.mask_sensitive_value('api_dashscope_api_key'),
            "api_openai_api_key": secure_manager.mask_sensitive_value('api_openai_api_key'),
            "api_gemini_api_key": secure_manager.mask_sensitive_value('api_gemini_api_key'),
            "api_siliconflow_api_key": secure_manager.mask_sensitive_value('api_siliconflow_api_key'),
            "api_zhipu_api_key": secure_manager.mask_sensitive_value('api_zhipu_api_key'),
            "api_tencent_api_key": secure_manager.mask_sensitive_value('api_tencent_api_key'),
            "api_ollama_api_key": secure_manager.mask_sensitive_value('api_ollama_api_key'),
            "dashscope_api_key": secure_manager.mask_sensitive_value('api_dashscope_api_key'),
            "openai_api_key": secure_manager.mask_sensitive_value('api_openai_api_key'),
            "gemini_api_key": secure_manager.mask_sensitive_value('api_gemini_api_key'),
            "siliconflow_api_key": secure_manager.mask_sensitive_value('api_siliconflow_api_key'),
            "zhipu_api_key": secure_manager.mask_sensitive_value('api_zhipu_api_key'),
            "tencent_api_key": secure_manager.mask_sensitive_value('api_tencent_api_key'),
            "ollama_api_key": secure_manager.mask_sensitive_value('api_ollama_api_key'),
            "ollama_base_url": secure_manager.get('ollama_base_url', 'http://localhost:11434/v1'),
            "ollama_cached_models": secure_manager.get('ollama_cached_models', '[]'),
            # 标记是否有密钥（用于前端判断）
            "has_dashscope_key": secure_manager.has_sensitive_value('api_dashscope_api_key') or bool(settings.api_dashscope_api_key),
            "has_openai_key": secure_manager.has_sensitive_value('api_openai_api_key'),
            "has_gemini_key": secure_manager.has_sensitive_value('api_gemini_api_key'),
            "has_siliconflow_key": secure_manager.has_sensitive_value('api_siliconflow_api_key'),
            "has_zhipu_key": secure_manager.has_sensitive_value('api_zhipu_api_key'),
            "has_tencent_key": secure_manager.has_sensitive_value('api_tencent_api_key'),
            "has_ollama_key": secure_manager.has_sensitive_value('api_ollama_api_key'),
        }
        
        logger.info("安全配置获取成功")
        return result
        
    except Exception as e:
        logger.error(f"获取安全配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# 兼容前端旧API端点（返回完整密钥用于回显）
# ========================================

@router.get("")
def get_settings():
    """
    获取系统配置（兼容前端旧API）
    注意：此接口返回完整的API Key用于表单回显
    """
    try:
        settings = _get_default_settings()
        secure_manager = _get_secure_manager()
        
        llm_provider = secure_manager.get('llm_provider', 'dashscope')
        model_name = secure_manager.get('model_name', settings.api_model_name)
        
        return {
            "llm_provider": llm_provider,
            "model_name": model_name,
            "chunk_size": secure_manager.get('chunk_size', settings.processing_chunk_size),
            "min_score_threshold": secure_manager.get('min_score_threshold', settings.processing_min_score_threshold),
            "max_clips_per_collection": secure_manager.get('max_clips_per_collection', settings.processing_max_clips_per_collection),
            "speech_recognition_method": secure_manager.get('speech_recognition_method', 'funasr'),
            "speech_recognition_model": secure_manager.get('speech_recognition_model', 'base'),
            # 返回实际密钥用于回显（仅本地应用安全）
            "api_dashscope_api_key": settings.api_dashscope_api_key or secure_manager.get_sensitive_value('api_dashscope_api_key'),
            "api_openai_api_key": secure_manager.get_sensitive_value('api_openai_api_key'),
            "api_gemini_api_key": secure_manager.get_sensitive_value('api_gemini_api_key'),
            "api_siliconflow_api_key": secure_manager.get_sensitive_value('api_siliconflow_api_key'),
            "api_zhipu_api_key": secure_manager.get_sensitive_value('api_zhipu_api_key'),
            "api_tencent_api_key": secure_manager.get_sensitive_value('api_tencent_api_key'),
            "api_ollama_api_key": secure_manager.get_sensitive_value('api_ollama_api_key'),
            "api_lmstudio_api_key": secure_manager.get_sensitive_value('api_lmstudio_api_key'),
            # 同时返回无 api_ 前缀的格式兼容前端
            "dashscope_api_key": settings.api_dashscope_api_key or secure_manager.get_sensitive_value('api_dashscope_api_key'),
            "openai_api_key": secure_manager.get_sensitive_value('api_openai_api_key'),
            "gemini_api_key": secure_manager.get_sensitive_value('api_gemini_api_key'),
            "siliconflow_api_key": secure_manager.get_sensitive_value('api_siliconflow_api_key'),
            "zhipu_api_key": secure_manager.get_sensitive_value('api_zhipu_api_key'),
            "tencent_api_key": secure_manager.get_sensitive_value('api_tencent_api_key'),
            "ollama_api_key": secure_manager.get_sensitive_value('api_ollama_api_key'),
            "lmstudio_api_key": secure_manager.get_sensitive_value('api_lmstudio_api_key'),
            "ollama_base_url": secure_manager.get('ollama_base_url', 'http://localhost:11434/v1'),
            "lmstudio_base_url": secure_manager.get('lmstudio_base_url', 'http://localhost:1234/v1'),
            "ollama_cached_models": secure_manager.get('ollama_cached_models', '[]'),
            "lmstudio_cached_models": secure_manager.get('lmstudio_cached_models', '[]'),
        }
    except Exception as e:
        logger.error(f"获取配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def update_settings(settings_data: Dict[str, Any]):
    """
    更新系统配置（兼容前端旧API）
    敏感数据会自动加密存储
    """
    try:
        secure_manager = _get_secure_manager()
        
        logger.info(f"保存配置: {list(settings_data.keys())}")
        
        # 兼容前端：把无 api_ 前缀的字段转换成有 api_ 前缀的
        field_mapping = {
            'dashscope_api_key': 'api_dashscope_api_key',
            'openai_api_key': 'api_openai_api_key',
            'gemini_api_key': 'api_gemini_api_key',
            'siliconflow_api_key': 'api_siliconflow_api_key',
            'zhipu_api_key': 'api_zhipu_api_key',
            'tencent_api_key': 'api_tencent_api_key',
            'ollama_api_key': 'api_ollama_api_key',
            'lmstudio_api_key': 'api_lmstudio_api_key',
        }
        
        for frontend_field, backend_field in field_mapping.items():
            if frontend_field in settings_data:
                settings_data[backend_field] = settings_data[frontend_field]
        
        # 使用安全配置管理器保存（自动加密敏感字段）
        secure_manager.update(settings_data)

        # 同步非敏感字段到 settings.json（LLMManager 从该文件读取）
        _sync_settings_to_json(settings_data)

        # 同步运行中的 LLMManager，使新配置立即生效
        from backend.core.llm_manager import get_llm_manager
        try:
            llm_manager = get_llm_manager()
            llm_manager.update_settings(settings_data)
            logger.info(f"LLMManager 已更新: {settings_data.get('llm_provider')} / {settings_data.get('model_name')}")
        except Exception as e:
            logger.warning(f"LLMManager 更新失败（不影响配置保存）: {e}")

        return {
            "success": True,
            "message": "配置保存成功",
            "data": settings_data
        }
    except Exception as e:
        logger.error(f"更新配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _sync_settings_to_json(settings_data: Dict[str, Any]):
    """将非敏感配置同步到 settings.json（供 LLMManager 读取）"""
    try:
        settings_path = Path(__file__).parent.parent.parent.parent / "data" / "settings.json"
        if not settings_path.exists():
            return

        with open(settings_path, 'r', encoding='utf-8') as f:
            current = json.load(f)

        # 只同步非敏感字段（敏感字段由 secure_config_manager 管理）
        sync_fields = {'llm_provider', 'model_name', 'ollama_base_url', 'lmstudio_base_url',
                       'chunk_size', 'min_score_threshold', 'max_clips_per_collection'}
        changed = False
        for key in sync_fields:
            if key in settings_data and settings_data[key] != current.get(key):
                current[key] = settings_data[key]
                changed = True

        if changed:
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
            logger.info(f"已同步非敏感配置到 settings.json")
    except Exception as e:
        logger.warning(f"同步配置到 settings.json 失败: {e}")


@router.post("/test-api-key")
def test_api_key(data: Dict[str, Any]):
    """
    测试API密钥
    """
    try:
        provider = data.get("provider", "")
        api_key = data.get("api_key", "")
        model_name = data.get("model_name", "")
        
        logger.info(f"测试API密钥: provider={provider}, model={model_name}")
        
        # Ollama/LM Studio是本地模型，不需要API Key
        if provider == "ollama":
            try:
                import requests
                base_url = data.get("base_url", "http://localhost:11434/v1")
                # 测试Ollama服务是否在运行
                resp = requests.get(base_url.replace("/v1", "") + "/api/tags", timeout=5)
                if resp.status_code == 200:
                    return {
                        "success": True,
                        "message": f"Ollama连接成功，已安装 {len(resp.json().get('models', []))} 个模型"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Ollama服务返回异常: {resp.status_code}"
                    }
            except requests.exceptions.ConnectionError:
                return {
                    "success": False,
                    "error": f"无法连接Ollama服务 ({base_url})，请确认Ollama已启动"
                }
            except Exception as e:
                logger.error(f"Ollama连接测试失败: {e}")
                return {
                    "success": False,
                    "error": f"Ollama连接测试失败: {str(e)}"
                }

        if provider == "lmstudio":
            try:
                import requests
                base_url = data.get("base_url", "http://localhost:1234/v1")
                base_url = base_url.rstrip('/') if base_url else "http://localhost:1234/v1"
                resp = requests.get(f"{base_url}/models", timeout=10)
                if resp.status_code == 200:
                    models = resp.json().get("data", [])
                    return {
                        "success": True,
                        "message": f"LM Studio连接成功，已加载 {len(models)} 个模型"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"LM Studio返回异常: {resp.status_code}"
                    }
            except requests.exceptions.ConnectionError:
                return {
                    "success": False,
                    "error": f"无法连接LM Studio ({base_url})，请确认LM Studio已启动并开启Server"
                }
            except Exception as e:
                logger.error(f"LM Studio连接测试失败: {e}")
                return {
                    "success": False,
                    "error": f"LM Studio连接测试失败: {str(e)}"
                }
        
        if not api_key:
            return {
                "success": False,
                "error": "API密钥不能为空"
            }
        
        if len(api_key) < 10:
            return {
                "success": False,
                "error": "API密钥长度不足"
            }
        
        # 实际调用API测试Key有效性
        try:
            from backend.core.llm_manager import get_llm_manager
            from backend.core.llm_providers import ProviderType
            llm_manager = get_llm_manager()
            provider_type = ProviderType(provider)
            result = llm_manager.test_provider_connection(provider_type, api_key, model_name)
            if result:
                return {
                    "success": True,
                    "message": "API密钥验证通过"
                }
            else:
                return {
                    "success": False,
                    "error": "API密钥验证失败，请检查密钥是否正确或是否已过期"
                }
        except Exception as e:
            logger.error(f"API密钥测试失败: {e}")
            return {
                "success": False,
                "error": f"API密钥验证失败: {str(e)}"
            }
    except Exception as e:
        logger.error(f"测试API密钥失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/available-models")
def get_available_models():
    """
    获取所有可用模型
    """
    return {
        "zhipu": [
            {"name": "glm-4-flash", "display_name": "GLM-4-Flash", "max_tokens": 128000, "description": "智谱AI GLM-4-Flash模型（免费版）"},
            {"name": "glm-4", "display_name": "GLM-4", "max_tokens": 128000, "description": "智谱AI GLM-4模型"},
            {"name": "glm-4-plus", "display_name": "GLM-4-Plus", "max_tokens": 128000, "description": "智谱AI GLM-4-Plus模型"}
        ],
        "dashscope": [
            {"name": "qwen-plus", "display_name": "通义千问Plus", "max_tokens": 8192, "description": "通义千问Plus模型"},
            {"name": "qwen-max", "display_name": "通义千问Max", "max_tokens": 8192, "description": "通义千问Max模型"},
            {"name": "qwen-turbo", "display_name": "通义千问Turbo", "max_tokens": 8192, "description": "通义千问Turbo模型"}
        ],
        "openai": [
            {"name": "gpt-3.5-turbo", "display_name": "GPT-3.5 Turbo", "max_tokens": 16385, "description": "OpenAI GPT-3.5 Turbo模型"},
            {"name": "gpt-4", "display_name": "GPT-4", "max_tokens": 8192, "description": "OpenAI GPT-4模型"},
            {"name": "gpt-4-turbo", "display_name": "GPT-4 Turbo", "max_tokens": 128000, "description": "OpenAI GPT-4 Turbo模型"}
        ],
        "gemini": [
            {"name": "gemini-2.5-flash", "display_name": "Gemini 2.5 Flash", "max_tokens": 1000000, "description": "Google Gemini 2.5 Flash模型"},
            {"name": "gemini-1.5-pro", "display_name": "Gemini 1.5 Pro", "max_tokens": 1000000, "description": "Google Gemini 1.5 Pro模型"},
            {"name": "gemini-1.5-flash", "display_name": "Gemini 1.5 Flash", "max_tokens": 1000000, "description": "Google Gemini 1.5 Flash模型"}
        ],
        "siliconflow": [
            {"name": "Qwen/Qwen2.5-7B-Instruct", "display_name": "Qwen2.5-7B", "max_tokens": 8192, "description": "Qwen2.5-7B开源模型"},
            {"name": "Qwen/Qwen2.5-14B-Instruct", "display_name": "Qwen2.5-14B", "max_tokens": 8192, "description": "Qwen2.5-14B开源模型"},
            {"name": "Qwen2.5-32B-Instruct", "display_name": "Qwen2.5-32B", "max_tokens": 8192, "description": "Qwen2.5-32B开源模型"},
            {"name": "deepseek-ai/DeepSeek-V2.5", "display_name": "DeepSeek-V2.5", "max_tokens": 8192, "description": "DeepSeek-V2.5开源模型"}
        ],
        "tencent": [
            {"name": "hunyuan-pro", "display_name": "混元大模型Pro", "max_tokens": 8192, "description": "腾讯混元Pro模型"},
            {"name": "hunyuan-lite", "display_name": "混元大模型Lite", "max_tokens": 8192, "description": "腾讯混元Lite模型"},
            {"name": "hunyuan-standard", "display_name": "混元大模型标准版", "max_tokens": 8192, "description": "腾讯混元标准版模型"}
        ],
        "ollama": [],
        "lmstudio": [],
    }


@router.get("/ollama-local-models")
def get_ollama_local_models(base_url: str = "http://localhost:11434/v1"):
    """
    获取本地Ollama已下载的模型列表（动态调用Ollama API）
    """
    try:
        import requests
        ollama_api_base = base_url.replace("/v1", "").rstrip("/")
        resp = requests.get(f"{ollama_api_base}/api/tags", timeout=5)
        if resp.status_code != 200:
            return {"models": [], "error": f"Ollama返回异常: {resp.status_code}"}

        data = resp.json()
        models = data.get("models", [])
        result = []
        for m in models:
            name = m["name"]
            size_gb = round(m["size"] / (1024**3), 1) if m.get("size") else 0
            result.append({
                "name": name,
                "display_name": f"{name} ({size_gb}GB)",
                "max_tokens": 32768,
                "description": f"本地已安装 · {size_gb}GB"
            })
        return {"models": result}

    except requests.exceptions.ConnectionError:
        return {"models": [], "error": f"无法连接Ollama服务 ({base_url})，请确认Ollama已启动"}
    except Exception as e:
        logger.error(f"获取Ollama本地模型失败: {e}")
        return {"models": [], "error": str(e)}


@router.post("/refresh-ollama-models")
def refresh_ollama_models(data: Dict[str, Any]):
    """
    刷新Ollama本地模型列表，并将结果缓存到设置中
    """
    try:
        base_url = data.get("base_url", "http://localhost:11434/v1")
        secure_manager = _get_secure_manager()

        import requests
        ollama_api_base = base_url.replace("/v1", "").rstrip("/")
        resp = requests.get(f"{ollama_api_base}/api/tags", timeout=5)

        if resp.status_code != 200:
            return {"models": [], "error": f"Ollama返回异常: {resp.status_code}"}

        data = resp.json()
        models = data.get("models", [])
        result = []
        for m in models:
            name = m["name"]
            size_gb = round(m["size"] / (1024**3), 1) if m.get("size") else 0
            result.append({
                "name": name,
                "display_name": f"{name} ({size_gb}GB)",
                "max_tokens": 32768,
                "description": f"本地已安装 · {size_gb}GB"
            })

        # 缓存到设置中
        secure_manager.update({"ollama_cached_models": json.dumps(result)})

        return {"models": result, "cached": True}

    except requests.exceptions.ConnectionError:
        return {"models": [], "error": f"无法连接Ollama服务 ({base_url})，请确认Ollama已启动"}
    except Exception as e:
        logger.error(f"刷新Ollama模型失败: {e}")
        return {"models": [], "error": str(e)}


def get_lmstudio_local_models(base_url: str = "http://localhost:1234/v1"):
    """
    获取本地LM Studio已加载的模型列表（调用LM Studio API）
    """
    try:
        import requests
        resp = requests.get(f"{base_url}/models", timeout=5)
        if resp.status_code != 200:
            return {"models": [], "error": f"LM Studio返回异常: {resp.status_code}"}

        data = resp.json()
        models = data.get("data", [])
        result = []
        for m in models:
            name = m["id"]
            result.append({
                "name": name,
                "display_name": name,
                "max_tokens": 32768,
                "description": "本地已加载"
            })
        return {"models": result}

    except requests.exceptions.ConnectionError:
        return {"models": [], "error": f"无法连接LM Studio ({base_url})，请确认LM Studio已启动并开启Server"}
    except Exception as e:
        logger.error(f"获取LM Studio本地模型失败: {e}")
        return {"models": [], "error": str(e)}


@router.post("/refresh-lmstudio-models")
def refresh_lmstudio_models(data: Dict[str, Any]):
    """
    刷新LM Studio本地模型列表，并将结果缓存到设置中
    """
    try:
        base_url = data.get("base_url", "http://localhost:1234/v1")
        base_url = base_url.rstrip('/') if base_url else "http://localhost:1234/v1"
        secure_manager = _get_secure_manager()

        import requests
        resp = requests.get(f"{base_url}/models", timeout=10)

        if resp.status_code != 200:
            return {"models": [], "error": f"LM Studio返回异常: {resp.status_code}"}

        data = resp.json()
        models = data.get("data", [])
        result = []
        for m in models:
            name = m["id"]
            result.append({
                "name": name,
                "display_name": name,
                "max_tokens": 32768,
                "description": "本地已加载"
            })

        # 缓存到设置中
        secure_manager.update({"lmstudio_cached_models": json.dumps(result)})

        return {"models": result, "cached": True}

    except requests.exceptions.ConnectionError:
        return {"models": [], "error": f"无法连接LM Studio ({base_url})，请确认LM Studio已启动并开启Server"}
    except Exception as e:
        logger.error(f"刷新LM Studio模型失败: {e}")
        return {"models": [], "error": str(e)}


@router.get("/current-provider")
def get_current_provider():
    """
    获取当前提供商信息
    """
    try:
        settings = _get_default_settings()
        secure_manager = _get_secure_manager()
        
        llm_provider = secure_manager.get('llm_provider', 'dashscope')
        model_name = secure_manager.get('model_name', settings.api_model_name)
        
        # 检查是否有有效的API Key
        provider_key_map = {
            'dashscope': 'api_dashscope_api_key',
            'openai': 'api_openai_api_key',
            'gemini': 'api_gemini_api_key',
            'siliconflow': 'api_siliconflow_api_key',
            'zhipu': 'api_zhipu_api_key',
            'tencent': 'api_tencent_api_key',
            'ollama': 'api_ollama_api_key',
            'lmstudio': 'api_lmstudio_api_key',
        }
        
        key_name = provider_key_map.get(llm_provider, 'api_dashscope_api_key')
        has_key = secure_manager.has_sensitive_value(key_name)
        
        if llm_provider == 'dashscope' and not has_key:
            has_key = bool(settings.api_dashscope_api_key)
        
        # Ollama/LM Studio是本地服务，即使没有API Key也视为可用
        if llm_provider in ('ollama', 'lmstudio'):
            has_key = True
        
        provider_names = {
            "dashscope": "阿里通义千问",
            "zhipu": "智谱AI",
            "openai": "OpenAI",
            "gemini": "Google Gemini",
            "siliconflow": "硅基流动",
            "tencent": "腾讯混元",
            "ollama": "本地Ollama",
            "lmstudio": "本地LM Studio"
        }
        
        return {
            "provider": llm_provider,
            "model": model_name,
            "display_name": provider_names.get(llm_provider, llm_provider),
            "available": has_key
        }
    except Exception as e:
        logger.error(f"获取当前提供商失败: {e}", exc_info=True)
        return {
            "provider": "dashscope",
            "model": "qwen-plus",
            "display_name": "阿里通义千问",
            "available": False
        }


@router.get("/speech-recognition-methods")
def get_speech_recognition_methods():
    """
    获取所有可用的语音识别方法
    """
    return {
        "funasr": {
            "name": "FunASR 语音识别",
            "description": "阿里开源FunASR模型，中文识别准确率高，完全离线可用",
            "requires_api_key": False,
            "requires_network": False,
            "available": True,
            "models": ["paraformer-zh"]
        },
        "whisper_local": {
            "name": "Whisper 本地识别",
            "description": "OpenAI Whisper开源模型，完全离线可用",
            "requires_api_key": False,
            "requires_network": False,
            "available": True,
            "models": ["tiny", "base", "small", "medium", "large"]
        },
        "bcut_asr": {
            "name": "B站必剪ASR",
            "description": "B站必剪语音识别服务，需要网络连接",
            "requires_api_key": False,
            "requires_network": True,
            "available": True,
            "models": ["default"]
        },
        "openai_api": {
            "name": "OpenAI Whisper API",
            "description": "OpenAI官方Whisper API，需要API Key",
            "requires_api_key": True,
            "requires_network": True,
            "available": True,
            "models": ["whisper-1"]
        },
        "azure_speech": {
            "name": "Azure 语音服务",
            "description": "微软Azure语音识别服务",
            "requires_api_key": True,
            "requires_network": True,
            "available": False,
            "models": ["default"]
        },
        "google_speech": {
            "name": "Google 语音识别",
            "description": "Google Cloud语音识别服务",
            "requires_api_key": True,
            "requires_network": True,
            "available": False,
            "models": ["default"]
        },
        "aliyun_speech": {
            "name": "阿里云语音识别",
            "description": "阿里云智能语音服务",
            "requires_api_key": True,
            "requires_network": True,
            "available": False,
            "models": ["default"]
        }
    }


@router.get("/health")
def health_check():
    """健康检查"""
    return {"status": "healthy"}


# ========================================
# 密钥管理API（仅供管理员使用）
# ========================================

@router.post("/security/backup-key")
def backup_key(data: Dict[str, str]):
    """
    备份加密密钥
    :param backup_path: 备份文件路径（可选）
    """
    try:
        secure_manager = _get_secure_manager()
        
        backup_path = data.get('backup_path')
        if backup_path:
            success = secure_manager.backup_key(Path(backup_path))
        else:
            # 默认备份路径
            backup_path = secure_manager._KEY_DIR / f"encryption.key.backup"
            success = secure_manager.backup_key(backup_path)
        
        return {
            "success": success,
            "message": "密钥备份成功" if success else "密钥备份失败",
            "backup_path": str(backup_path)
        }
    except Exception as e:
        logger.error(f"备份密钥失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/security/restore-key")
def restore_key(data: Dict[str, str]):
    """
    从备份恢复加密密钥
    :param backup_path: 备份文件路径
    """
    try:
        secure_manager = _get_secure_manager()
        
        backup_path = data.get('backup_path')
        if not backup_path:
            raise HTTPException(status_code=400, detail="需要提供备份路径")
        
        success = secure_manager.restore_key(Path(backup_path))
        
        return {
            "success": success,
            "message": "密钥恢复成功" if success else "密钥恢复失败"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"恢复密钥失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/security/rotate-key")
def rotate_key():
    """
    密钥轮换 - 生成新密钥并重新加密所有数据
    """
    try:
        secure_manager = _get_secure_manager()
        
        success = secure_manager.rotate_key()
        
        return {
            "success": success,
            "message": "密钥轮换成功" if success else "密钥轮换失败"
        }
    except Exception as e:
        logger.error(f"密钥轮换失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
