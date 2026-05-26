"""
LLM管理器 - 统一管理多个模型提供商
"""
import json
import logging
import os
from typing import Dict, Any, Optional, List
from pathlib import Path

from .llm_providers import (
    LLMProvider, LLMProviderFactory, ProviderType, 
    ModelInfo, LLMResponse
)

logger = logging.getLogger(__name__)

class LLMManager:
    """LLM管理器"""
    
    def __init__(self, settings_file: Optional[Path] = None):
        self.settings_file = settings_file or self._get_default_settings_file()
        self.current_provider: Optional[LLMProvider] = None
        self.settings = self._load_settings()
        self._initialize_provider()
    
    def _get_default_settings_file(self) -> Path:
        """获取默认设置文件路径"""
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent  # backend/core -> backend -> project_root
        return project_root / "data" / "settings.json"
    
    def _load_settings(self) -> Dict[str, Any]:
        """加载设置"""
        default_settings = {
            "llm_provider": "dashscope",
            "dashscope_api_key": "",
            "openai_api_key": "",
            "gemini_api_key": "",
            "siliconflow_api_key": "",
            "zhipu_api_key": "",
            "tencent_api_key": "",
            "ollama_api_key": "",
            "ollama_base_url": "http://localhost:11434/v1",
            "lmstudio_api_key": "",
            "lmstudio_base_url": "http://localhost:1234/v1",
            "model_name": "qwen-plus",
            "chunk_size": 5000,
            "min_score_threshold": 0.7,
            "max_clips_per_collection": 5
        }
        
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    default_settings.update(saved_settings)
            except Exception as e:
                logger.warning(f"加载设置文件失败: {e}")
        
        return default_settings
    
    def _save_settings(self):
        """保存设置"""
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存设置失败: {e}")
            raise
    
    def _initialize_provider(self):
        """初始化当前提供商"""
        try:
            provider_type = ProviderType(self.settings.get("llm_provider", "dashscope"))
            model_name = self.settings.get("model_name", "qwen-plus")
            
            # 获取对应提供商的API密钥
            api_key = self._get_api_key_for_provider(provider_type)
            
            if api_key or provider_type in (ProviderType.OLLAMA, ProviderType.LMSTUDIO):
                # Ollama/LM Studio可以没有API Key（本地连接），传入空字符串
                effective_api_key = api_key or ""
                if provider_type == ProviderType.OLLAMA:
                    base_url = self.settings.get("ollama_base_url", "http://localhost:11434/v1")
                    self.current_provider = LLMProviderFactory.create_provider(
                        provider_type, effective_api_key, model_name, base_url=base_url
                    )
                elif provider_type == ProviderType.LMSTUDIO:
                    base_url = self.settings.get("lmstudio_base_url", "http://localhost:1234/v1")
                    self.current_provider = LLMProviderFactory.create_provider(
                        provider_type, effective_api_key, model_name, base_url=base_url
                    )
                else:
                    self.current_provider = LLMProviderFactory.create_provider(
                        provider_type, effective_api_key, model_name
                    )
                logger.info(f"已初始化{provider_type.value}提供商，模型: {model_name}")
            else:
                logger.warning(f"未找到{provider_type.value}的API密钥")
                
        except Exception as e:
            logger.error(f"初始化提供商失败: {e}")
            self.current_provider = None

    def _get_api_key_for_provider(self, provider_type: ProviderType) -> Optional[str]:
        """获取指定提供商的API密钥"""
        key_mapping = {
            ProviderType.DASHSCOPE: "dashscope_api_key",
            ProviderType.OPENAI: "openai_api_key",
            ProviderType.GEMINI: "gemini_api_key",
            ProviderType.SILICONFLOW: "siliconflow_api_key",
            ProviderType.ZHIPU: "zhipu_api_key",
            ProviderType.TENCENT: "tencent_api_key",
            ProviderType.OLLAMA: "ollama_api_key",
            ProviderType.LMSTUDIO: "lmstudio_api_key",
        }
        
        key_name = key_mapping.get(provider_type)
        if key_name:
            return self.settings.get(key_name, "")
        return None
    
    def update_settings(self, new_settings: Dict[str, Any]):
        """更新设置"""
        self.settings.update(new_settings)
        self._save_settings()
        self._initialize_provider()
    
    def set_provider(self, provider_type: ProviderType, api_key: str, model_name: str):
        """设置提供商"""
        try:
            # 更新设置
            provider_settings = {
                "llm_provider": provider_type.value,
                "model_name": model_name
            }
            
            # 更新对应提供商的API密钥
            key_mapping = {
                ProviderType.DASHSCOPE: "dashscope_api_key",
                ProviderType.OPENAI: "openai_api_key",
                ProviderType.GEMINI: "gemini_api_key",
                ProviderType.SILICONFLOW: "siliconflow_api_key",
                ProviderType.ZHIPU: "zhipu_api_key",
                ProviderType.TENCENT: "tencent_api_key",
                ProviderType.OLLAMA: "ollama_api_key",
                ProviderType.LMSTUDIO: "lmstudio_api_key",
            }
            
            key_name = key_mapping.get(provider_type)
            if key_name:
                provider_settings[key_name] = api_key
            
            self.update_settings(provider_settings)
            
            # 创建新的提供商实例
            if provider_type == ProviderType.OLLAMA:
                base_url = self.settings.get("ollama_base_url", "http://localhost:11434/v1")
                self.current_provider = LLMProviderFactory.create_provider(
                    provider_type, api_key, model_name, base_url=base_url
                )
            elif provider_type == ProviderType.LMSTUDIO:
                base_url = self.settings.get("lmstudio_base_url", "http://localhost:1234/v1")
                self.current_provider = LLMProviderFactory.create_provider(
                    provider_type, api_key, model_name, base_url=base_url
                )
            else:
                self.current_provider = LLMProviderFactory.create_provider(
                    provider_type, api_key, model_name
                )
            
            logger.info(f"已切换到{provider_type.value}提供商，模型: {model_name}")
            
        except Exception as e:
            logger.error(f"设置提供商失败: {e}")
            raise
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> str:
        """调用LLM"""
        if not self.current_provider:
            raise ValueError("未配置LLM提供商，请在设置页面配置API密钥")
        
        try:
            response = self.current_provider.call(prompt, input_data, **kwargs)
            return response.content
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise
    
    def call_with_retry(self, prompt: str, input_data: Any = None, max_retries: int = 3, timeout: int = 60, **kwargs) -> str:
        """带重试机制的LLM调用"""
        import time
        for attempt in range(max_retries):
            try:
                return self.call(prompt, input_data, **kwargs)
            except ValueError:  # 如果是API Key或参数错误，不重试
                raise
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"LLM调用在{max_retries}次重试后彻底失败。")
                    raise RuntimeError(f"LLM调用在{max_retries}次重试后彻底失败: {e}") from e
                logger.warning(f"第{attempt + 1}次调用失败，准备重试: {str(e)}")
                wait_time = min(2 ** attempt, 30)  # 指数退避，最大等待30秒
                time.sleep(wait_time)
        raise RuntimeError(f"LLM调用在{max_retries}次重试后彻底失败")
    
    def test_provider_connection(self, provider_type: ProviderType, api_key: str, model_name: str) -> bool:
        """测试提供商连接"""
        try:
            provider = LLMProviderFactory.create_provider(provider_type, api_key, model_name)
            return provider.test_connection()
        except Exception as e:
            logger.error(f"测试{provider_type.value}连接失败: {e}")
            return False
    
    def get_current_provider_info(self) -> Dict[str, Any]:
        """获取当前提供商信息"""
        if not self.current_provider:
            return {"provider": None, "model": None, "available": False}
        
        provider_type = ProviderType(self.settings.get("llm_provider", "dashscope"))
        model_name = self.settings.get("model_name", "qwen-plus")
        
        return {
            "provider": provider_type.value,
            "model": model_name,
            "available": True,
            "display_name": self._get_provider_display_name(provider_type)
        }
    
    def _get_provider_display_name(self, provider_type: ProviderType) -> str:
        """获取提供商显示名称"""
        display_names = {
            ProviderType.DASHSCOPE: "阿里通义千问",
            ProviderType.OPENAI: "OpenAI",
            ProviderType.GEMINI: "Google Gemini",
            ProviderType.SILICONFLOW: "硅基流动",
            ProviderType.ZHIPU: "智谱AI",
            ProviderType.TENCENT: "腾讯混元",
            ProviderType.OLLAMA: "本地Ollama",
            ProviderType.LMSTUDIO: "本地LM Studio"
        }
        return display_names.get(provider_type, provider_type.value)
    
    def get_all_available_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有可用模型"""
        all_models = LLMProviderFactory.get_all_available_models()
        result = {}
        
        for provider_type, models in all_models.items():
            provider_name = provider_type.value
            result[provider_name] = [
                {
                    "name": model.name,
                    "display_name": model.display_name,
                    "max_tokens": model.max_tokens,
                    "description": model.description
                }
                for model in models
            ]
        
        return result
    
    def parse_json_response(self, response: str) -> Any:
        """解析JSON响应，支持清理尾逗号等LLM常见错误"""
        if not self.current_provider:
            raise ValueError("未配置LLM提供商")

        import json
        import re

        def clean_trailing_commas(text: str) -> str:
            return re.sub(r',\s*([\]}])', r'\1', text)

        # 1. 直接解析
        try:
            return json.loads(clean_trailing_commas(response))
        except json.JSONDecodeError:
            pass

        # 2. 从 ```json ``` 代码块中提取
        for block in re.findall(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response):
            start = block.find('[') if '[' in block else block.find('{')
            end = block.rfind(']') if ']' in block else block.rfind('}')
            if start >= 0 and end > start:
                try:
                    return json.loads(clean_trailing_commas(block[start:end + 1]))
                except json.JSONDecodeError:
                    pass

        # 3. 从文本中提取第一个 JSON 数组或对象
        for open_b, close_b in [('[', ']'), ('{', '}')]:
            start = response.find(open_b)
            end = response.rfind(close_b)
            if start >= 0 and end > start:
                try:
                    return json.loads(clean_trailing_commas(response[start:end + 1]))
                except json.JSONDecodeError:
                    pass

        logger.warning(f"无法解析LLM响应，响应长度: {len(response)}")
        return None

# 全局LLM管理器实例
_llm_manager: Optional[LLMManager] = None

def get_llm_manager() -> LLMManager:
    """获取全局LLM管理器实例"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager

def initialize_llm_manager(settings_file: Optional[Path] = None) -> LLMManager:
    """初始化LLM管理器"""
    global _llm_manager
    _llm_manager = LLMManager(settings_file)
    return _llm_manager
