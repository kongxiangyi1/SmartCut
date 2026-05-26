"""
多模型提供商统一接口
支持OpenAI、Gemini、硅基流动、阿里DashScope等
"""
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

class ProviderType(Enum):
    """模型提供商类型"""
    DASHSCOPE = "dashscope"  # 阿里通义千问
    OPENAI = "openai"        # OpenAI
    GEMINI = "gemini"        # Google Gemini
    SILICONFLOW = "siliconflow"  # 硅基流动
    ZHIPU = "zhipu"          # 智谱AI
    TENCENT = "tencent"      # 腾讯混元
    OLLAMA = "ollama"        # 本地Ollama
    LMSTUDIO = "lmstudio"    # 本地LM Studio

@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    display_name: str
    provider: ProviderType
    max_tokens: int
    cost_per_token: Optional[float] = None
    description: Optional[str] = None

@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    finish_reason: Optional[str] = None

class LLMProvider(ABC):
    """LLM提供商抽象基类"""
    
    def __init__(self, api_key: str, model_name: str, **kwargs):
        self.api_key = api_key
        self.model_name = model_name
        self.kwargs = kwargs
    
    @abstractmethod
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """
        调用模型API
        
        Args:
            prompt: 提示词
            input_data: 输入数据
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 模型响应
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        测试API连接
        
        Returns:
            bool: 连接是否成功
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[ModelInfo]:
        """
        获取可用模型列表
        
        Returns:
            List[ModelInfo]: 可用模型列表
        """
        pass
    
    def _format_input_data(self, input_data: Any = None) -> Optional[str]:
        """统一格式化输入数据：单key dict自动提取值，避免JSON包装噪声"""
        if input_data is None:
            return None
        if isinstance(input_data, dict):
            if len(input_data) == 1:
                return str(next(iter(input_data.values())))
            return json.dumps(input_data, ensure_ascii=False, indent=2)
        return str(input_data)
    
    def _build_full_input(self, prompt: str, input_data: Any = None) -> str:
        """构建完整的输入"""
        formatted = self._format_input_data(input_data)
        if formatted:
            return f"{prompt}\n\n输入内容：\n{formatted}"
        return prompt

class DashScopeProvider(LLMProvider):
    """阿里DashScope提供商"""
    
    def __init__(self, api_key: str, model_name: str = "qwen-plus", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        try:
            from dashscope import Generation
            self.generation = Generation
        except ImportError:
            raise ImportError("请安装dashscope: pip install dashscope")
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用DashScope API"""
        try:
            full_input = self._build_full_input(prompt, input_data)
            
            response_or_gen = self.generation.call(
                model=self.model_name,
                prompt=full_input,
                api_key=self.api_key,
                stream=False,
                **kwargs
            )
            
            # 处理响应
            # DashScope的GenerationResponse虽然有__iter__方法，但不是真正的迭代器
            # 直接使用响应对象本身
            response = response_or_gen
            
            if response and response.status_code == 200:
                if response.output and response.output.text is not None:
                    return LLMResponse(
                        content=response.output.text,
                        model=self.model_name,
                        finish_reason=getattr(response.output, 'finish_reason', None)
                    )
                else:
                    finish_reason = getattr(response.output, 'finish_reason', 'unknown') if response.output else 'unknown'
                    logger.warning(f"API请求成功，但输出为空。结束原因: {finish_reason}")
                    return LLMResponse(content="")
            else:
                code = getattr(response, 'code', 'N/A')
                message = getattr(response, 'message', '未知API错误')
                raise Exception(f"API调用失败 - Status: {response.status_code}, Code: {code}, Message: {message}")
                
        except Exception as e:
            logger.error(f"DashScope调用失败: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """测试DashScope连接"""
        try:
            response = self.call("请回复'测试成功'")
            return "测试成功" in response.content or "success" in response.content.lower()
        except Exception as e:
            logger.error(f"DashScope连接测试失败: {e}")
            return False
    
    @staticmethod
    def get_available_models() -> List[ModelInfo]:
        """获取DashScope可用模型"""
        return [
            ModelInfo(
                name="qwen-plus",
                display_name="通义千问Plus",
                provider=ProviderType.DASHSCOPE,
                max_tokens=8192,
                description="阿里云通义千问Plus模型"
            ),
            ModelInfo(
                name="qwen-max",
                display_name="通义千问Max",
                provider=ProviderType.DASHSCOPE,
                max_tokens=8192,
                description="阿里云通义千问Max模型"
            ),
            ModelInfo(
                name="qwen-turbo",
                display_name="通义千问Turbo",
                provider=ProviderType.DASHSCOPE,
                max_tokens=8192,
                description="阿里云通义千问Turbo模型"
            )
        ]

class OpenAIProvider(LLMProvider):
    """OpenAI提供商"""
    
    def __init__(self, api_key: str, model_name: str = "gpt-3.5-turbo", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        try:
            import openai
            self.client = openai.OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("请安装openai: pip install openai")
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用OpenAI API"""
        try:
            if input_data is not None:
                user_content = self._format_input_data(input_data)
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content}
                ]
            else:
                messages = [{"role": "user", "content": prompt}]

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **kwargs
            )

            content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None

            return LLMResponse(
                content=content,
                usage=usage,
                model=self.model_name,
                finish_reason=response.choices[0].finish_reason
            )

        except Exception as e:
            logger.error(f"OpenAI调用失败: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """测试OpenAI连接"""
        try:
            response = self.call("请回复'测试成功'")
            return "测试成功" in response.content or "success" in response.content.lower()
        except Exception as e:
            logger.error(f"OpenAI连接测试失败: {e}")
            return False
    
    @staticmethod
    def get_available_models() -> List[ModelInfo]:
        """获取OpenAI可用模型"""
        return [
            ModelInfo(
                name="gpt-3.5-turbo",
                display_name="GPT-3.5 Turbo",
                provider=ProviderType.OPENAI,
                max_tokens=4096,
                description="OpenAI GPT-3.5 Turbo模型"
            ),
            ModelInfo(
                name="gpt-4",
                display_name="GPT-4",
                provider=ProviderType.OPENAI,
                max_tokens=8192,
                description="OpenAI GPT-4模型"
            ),
            ModelInfo(
                name="gpt-4-turbo",
                display_name="GPT-4 Turbo",
                provider=ProviderType.OPENAI,
                max_tokens=128000,
                description="OpenAI GPT-4 Turbo模型"
            )
        ]

class GeminiProvider(LLMProvider):
    """Google Gemini提供商"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)
        except ImportError:
            raise ImportError("请安装google-generativeai: pip install google-generativeai")
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用Gemini API"""
        try:
            full_input = self._build_full_input(prompt, input_data)
            
            response = self.model.generate_content(full_input, **kwargs)
            
            return LLMResponse(
                content=response.text,
                model=self.model_name,
                finish_reason=getattr(response, 'finish_reason', None)
            )
            
        except Exception as e:
            logger.error(f"Gemini调用失败: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """测试Gemini连接"""
        try:
            response = self.call("请回复'测试成功'")
            return "测试成功" in response.content or "success" in response.content.lower()
        except Exception as e:
            logger.error(f"Gemini连接测试失败: {e}")
            return False
    
    @staticmethod
    def get_available_models() -> List[ModelInfo]:
        """获取Gemini可用模型"""
        return [
            ModelInfo(
                name="gemini-2.5-flash",
                display_name="Gemini 2.5 Flash",
                provider=ProviderType.GEMINI,
                max_tokens=1000000,
                description="Google Gemini 2.5 Flash模型"
            ),
            ModelInfo(
                name="gemini-1.5-pro",
                display_name="Gemini 1.5 Pro",
                provider=ProviderType.GEMINI,
                max_tokens=2000000,
                description="Google Gemini 1.5 Pro模型"
            ),
            ModelInfo(
                name="gemini-1.5-flash",
                display_name="Gemini 1.5 Flash",
                provider=ProviderType.GEMINI,
                max_tokens=1000000,
                description="Google Gemini 1.5 Flash模型"
            )
        ]

class SiliconFlowProvider(LLMProvider):
    """硅基流动提供商"""
    
    def __init__(self, api_key: str, model_name: str = "Qwen/Qwen2.5-7B-Instruct", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        try:
            import openai
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.siliconflow.cn/v1"
            )
        except ImportError:
            raise ImportError("请安装openai: pip install openai")
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用硅基流动API（OpenAI兼容接口）"""
        try:
            if input_data is not None:
                user_content = self._format_input_data(input_data)
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content}
                ]
            else:
                messages = [{"role": "user", "content": prompt}]

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **kwargs
            )

            content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None

            return LLMResponse(
                content=content,
                usage=usage,
                model=self.model_name,
                finish_reason=response.choices[0].finish_reason
            )

        except Exception as e:
            logger.error(f"硅基流动调用失败: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """测试硅基流动连接"""
        try:
            response = self.call("请回复'测试成功'")
            return "测试成功" in response.content or "success" in response.content.lower()
        except Exception as e:
            logger.error(f"硅基流动连接测试失败: {e}")
            return False
    
    @staticmethod
    def get_available_models() -> List[ModelInfo]:
        """获取硅基流动可用模型"""
        return [
            ModelInfo(
                name="Qwen/Qwen2.5-7B-Instruct",
                display_name="Qwen2.5-7B",
                provider=ProviderType.SILICONFLOW,
                max_tokens=32768,
                description="硅基流动Qwen2.5-7B模型"
            ),
            ModelInfo(
                name="Qwen/Qwen2.5-14B-Instruct",
                display_name="Qwen2.5-14B",
                provider=ProviderType.SILICONFLOW,
                max_tokens=32768,
                description="硅基流动Qwen2.5-14B模型"
            ),
            ModelInfo(
                name="Qwen/Qwen2.5-32B-Instruct",
                display_name="Qwen2.5-32B",
                provider=ProviderType.SILICONFLOW,
                max_tokens=32768,
                description="硅基流动Qwen2.5-32B模型"
            ),
            ModelInfo(
                name="deepseek-ai/DeepSeek-V2.5",
                display_name="DeepSeek-V2.5",
                provider=ProviderType.SILICONFLOW,
                max_tokens=65536,
                description="硅基流动DeepSeek-V2.5模型"
            )
        ]

class ZhipuProvider(LLMProvider):
    """智谱AI提供商"""
    
    def __init__(self, api_key: str, model_name: str = "glm-4-flash"):
        super().__init__(api_key, model_name)
        self.client = None
    
    def _init_client(self):
        """初始化客户端"""
        if self.client is None:
            try:
                from zhipuai import ZhipuAI
                self.client = ZhipuAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("请安装 zhipuai SDK: pip install zhipuai>=2.1.5")
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用智谱AI API"""
        self._init_client()
        
        try:
            if input_data is not None:
                user_content = self._format_input_data(input_data)
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content}
                ]
            else:
                messages = [{"role": "user", "content": prompt}]
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 2048),
                stream=False
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=self.model_name,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                finish_reason=response.choices[0].finish_reason
            )
            
        except Exception as e:
            logger.error(f"智谱AI调用失败: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """测试智谱AI连接"""
        try:
            response = self.call("请回复'测试成功'")
            return "测试成功" in response.content or "success" in response.content.lower()
        except Exception as e:
            logger.error(f"智谱AI连接测试失败: {e}")
            return False
    
    @staticmethod
    def get_available_models() -> List[ModelInfo]:
        """获取智谱AI可用模型"""
        return [
            ModelInfo(
                name="glm-4-flash",
                display_name="GLM-4-Flash",
                provider=ProviderType.ZHIPU,
                max_tokens=128000,
                description="智谱AI GLM-4-Flash模型（免费版）"
            ),
            ModelInfo(
                name="glm-4",
                display_name="GLM-4",
                provider=ProviderType.ZHIPU,
                max_tokens=128000,
                description="智谱AI GLM-4模型"
            ),
            ModelInfo(
                name="glm-4-plus",
                display_name="GLM-4-Plus",
                provider=ProviderType.ZHIPU,
                max_tokens=128000,
                description="智谱AI GLM-4-Plus模型"
            )
        ]

class TencentProvider(LLMProvider):
    """腾讯混元大模型提供商（OpenAI 兼容接口）"""

    def __init__(self, api_key: str, model_name: str = "hunyuan-turbo", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        try:
            import openai
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.hunyuan.cloud.tencent.com/v1"
            )
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用腾讯混元API（OpenAI兼容接口）"""
        try:
            if input_data is not None:
                user_content = self._format_input_data(input_data)
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content}
                ]
            else:
                messages = [{"role": "user", "content": prompt}]

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **kwargs
            )

            content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None

            return LLMResponse(
                content=content,
                usage=usage,
                model=self.model_name,
                finish_reason=response.choices[0].finish_reason
            )

        except Exception as e:
            logger.error(f"腾讯混元调用失败: {str(e)}")
            raise

    def test_connection(self) -> bool:
        """测试腾讯混元连接"""
        try:
            response = self.call("请回复'测试成功'")
            return "测试成功" in response.content or "success" in response.content.lower()
        except Exception as e:
            logger.error(f"腾讯混元连接测试失败: {e}")
            return False

    @staticmethod
    def get_available_models() -> List[ModelInfo]:
        """获取腾讯混元可用模型"""
        return [
            ModelInfo(
                name="hunyuan-turbos-latest",
                display_name="混元大模型Turbo最新版（推荐）",
                provider=ProviderType.TENCENT,
                max_tokens=8192,
                description="腾讯混元Turbo最新版本，响应快速效果好"
            ),
            ModelInfo(
                name="hunyuan-pro",
                display_name="混元大模型Pro",
                provider=ProviderType.TENCENT,
                max_tokens=8192,
                description="腾讯混元Pro版本，适合复杂任务"
            ),
            ModelInfo(
                name="hunyuan-lite",
                display_name="混元大模型Lite",
                provider=ProviderType.TENCENT,
                max_tokens=4096,
                description="腾讯混元Lite轻量版，响应更快"
            ),
            ModelInfo(
                name="hunyuan-standard",
                display_name="混元大模型标准版",
                provider=ProviderType.TENCENT,
                max_tokens=8192,
                description="腾讯混元标准版，平衡性能与成本"
            ),
            ModelInfo(
                name="hunyuan-standard-256K",
                display_name="混元大模型标准版256K",
                provider=ProviderType.TENCENT,
                max_tokens=256000,
                description="腾讯混元标准版，256K上下文"
            ),
            ModelInfo(
                name="hunyuan-functioncall",
                display_name="混元大模型函数调用版",
                provider=ProviderType.TENCENT,
                max_tokens=8192,
                description="腾讯混元函数调用版，支持Tool Use"
            ),
            ModelInfo(
                name="hunyuan-code",
                display_name="混元大模型代码版",
                provider=ProviderType.TENCENT,
                max_tokens=8192,
                description="腾讯混元代码版，专为代码优化"
            ),
            ModelInfo(
                name="hunyuan-vision",
                display_name="混元大模型视觉版",
                provider=ProviderType.TENCENT,
                max_tokens=4096,
                description="腾讯混元视觉版，支持图片理解"
            )
        ]

class OllamaProvider(LLMProvider):
    """本地Ollama大模型提供商（OpenAI 兼容接口）"""

    def __init__(self, api_key: str, model_name: str = "qwen2.5", base_url: str = "http://localhost:11434/v1", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        self.base_url = base_url
        try:
            import openai
            self.client = openai.OpenAI(
                api_key=api_key or "ollama",
                base_url=base_url,
                timeout=600.0,
                max_retries=0
            )
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用Ollama API（OpenAI兼容接口）"""
        try:
            messages = [{"role": "system", "content": prompt}]

            if input_data is not None:
                user_content = self._format_input_data(input_data)
                messages.append({"role": "user", "content": user_content})
            else:
                messages.append({"role": "user", "content": prompt})

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **kwargs
            )

            content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None

            return LLMResponse(
                content=content,
                usage=usage,
                model=self.model_name,
                finish_reason=response.choices[0].finish_reason
            )

        except Exception as e:
            logger.error(f"Ollama调用失败: {str(e)}")
            raise

    def test_connection(self) -> bool:
        """测试Ollama连接"""
        try:
            response = self.call("请回复'测试成功'")
            return "测试成功" in response.content or "success" in response.content.lower()
        except Exception as e:
            logger.error(f"Ollama连接测试失败: {e}")
            return False

    @staticmethod
    def get_available_models() -> List[ModelInfo]:
        """获取Ollama可用模型（返回常用本地模型列表）"""
        return [
            ModelInfo(
                name="qwen2.5",
                display_name="Qwen2.5（推荐）",
                provider=ProviderType.OLLAMA,
                max_tokens=32768,
                description="阿里通义千问Qwen2.5，需提前 pull"
            ),
            ModelInfo(
                name="qwen2.5:7b",
                display_name="Qwen2.5 7B",
                provider=ProviderType.OLLAMA,
                max_tokens=32768,
                description="阿里通义千问Qwen2.5 7B，需提前 pull"
            ),
            ModelInfo(
                name="qwen2.5:14b",
                display_name="Qwen2.5 14B",
                provider=ProviderType.OLLAMA,
                max_tokens=32768,
                description="阿里通义千问Qwen2.5 14B，需提前 pull"
            ),
            ModelInfo(
                name="qwen2.5:32b",
                display_name="Qwen2.5 32B",
                provider=ProviderType.OLLAMA,
                max_tokens=32768,
                description="阿里通义千问Qwen2.5 32B，需提前 pull"
            ),
            ModelInfo(
                name="llama3.1",
                display_name="Llama 3.1",
                provider=ProviderType.OLLAMA,
                max_tokens=32768,
                description="Meta Llama 3.1，需提前 pull"
            ),
            ModelInfo(
                name="llama3.1:8b",
                display_name="Llama 3.1 8B",
                provider=ProviderType.OLLAMA,
                max_tokens=32768,
                description="Meta Llama 3.1 8B，需提前 pull"
            ),
            ModelInfo(
                name="deepseek-r1:7b",
                display_name="DeepSeek R1 7B",
                provider=ProviderType.OLLAMA,
                max_tokens=32768,
                description="DeepSeek R1 7B，需提前 pull"
            ),
            ModelInfo(
                name="deepseek-r1:14b",
                display_name="DeepSeek R1 14B",
                provider=ProviderType.OLLAMA,
                max_tokens=32768,
                description="DeepSeek R1 14B，需提前 pull"
            ),
        ]

class LMStudioProvider(LLMProvider):
    """本地LM Studio大模型提供商（OpenAI 兼容接口）"""

    def __init__(self, api_key: str, model_name: str = "qwen2.5-7b-instruct", base_url: str = "http://localhost:1234/v1", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        self.base_url = base_url
        try:
            import openai
            self.client = openai.OpenAI(
                api_key=api_key or "lmstudio",
                base_url=base_url,
                timeout=3600.0,
                max_retries=0
            )
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用LM Studio API（OpenAI兼容接口）"""
        try:
            messages = [{"role": "system", "content": prompt}]

            if input_data is not None:
                user_content = self._format_input_data(input_data)
                messages.append({"role": "user", "content": user_content})
            else:
                messages.append({"role": "user", "content": prompt})

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **kwargs
            )

            content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None

            return LLMResponse(
                content=content,
                usage=usage,
                model=self.model_name,
                finish_reason=response.choices[0].finish_reason
            )

        except Exception as e:
            logger.error(f"LM Studio调用失败: {str(e)}")
            raise

    def test_connection(self) -> bool:
        """测试LM Studio连接"""
        try:
            response = self.call("请回复'测试成功'")
            return "测试成功" in response.content or "success" in response.content.lower()
        except Exception as e:
            logger.error(f"LM Studio连接测试失败: {e}")
            return False

    @staticmethod
    def get_available_models() -> List[ModelInfo]:
        """获取LM Studio可用模型（返回常用本地模型列表）"""
        return [
            ModelInfo(
                name="qwen2.5-7b-instruct",
                display_name="Qwen2.5 7B（推荐）",
                provider=ProviderType.LMSTUDIO,
                max_tokens=32768,
                description="通义千问Qwen2.5 7B，需在LM Studio中加载"
            ),
        ]


class LLMProviderFactory:
    """LLM提供商工厂"""
    
    _providers = {
        ProviderType.DASHSCOPE: DashScopeProvider,
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.GEMINI: GeminiProvider,
        ProviderType.SILICONFLOW: SiliconFlowProvider,
        ProviderType.ZHIPU: ZhipuProvider,
        ProviderType.TENCENT: TencentProvider,
        ProviderType.OLLAMA: OllamaProvider,
        ProviderType.LMSTUDIO: LMStudioProvider,
    }
    
    @classmethod
    def create_provider(cls, provider_type: ProviderType, api_key: str, model_name: str, **kwargs) -> LLMProvider:
        """创建提供商实例"""
        if provider_type not in cls._providers:
            raise ValueError(f"不支持的提供商类型: {provider_type}")
        
        provider_class = cls._providers[provider_type]
        return provider_class(api_key, model_name, **kwargs)
    
    @classmethod
    def get_all_available_models(cls) -> Dict[ProviderType, List[ModelInfo]]:
        """获取所有提供商的可用模型"""
        models = {}
        for provider_type, provider_class in cls._providers.items():
            try:
                # 直接调用静态方法，无需创建实例
                models[provider_type] = provider_class.get_available_models()
            except Exception as e:
                logger.warning(f"无法获取{provider_type.value}的模型列表: {e}")
                models[provider_type] = []
        return models
