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
    DEEPSEEK = "deepseek"    # DeepSeek
    MOARK = "moark"          # 模力方舟（Gitee AI，OpenAI兼容）
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

    def warmup(self):
        """预热模型（默认空实现，本地模型子类覆盖）"""
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

    def _resolve_prompt(self, prompt: str, input_data: Any = None) -> tuple:
        """
        解析 Prompt 占位符。

        Returns:
            (resolved_prompt, content_embedded)
        """
        formatted = self._format_input_data(input_data)
        if formatted and '{content}' in prompt:
            return prompt.replace('{content}', formatted), True
        return prompt, False

    def _build_full_input(self, prompt: str, input_data: Any = None) -> str:
        """构建完整的输入"""
        resolved, content_embedded = self._resolve_prompt(prompt, input_data)
        if content_embedded:
            return resolved

        formatted = self._format_input_data(input_data)
        if formatted:
            return f"{resolved}\n\n输入内容：\n{formatted}"

        if '{content}' in resolved:
            return resolved.replace('{content}', '')
        return resolved

    def _build_chat_messages(self, prompt: str, input_data: Any = None) -> List[Dict[str, str]]:
        """构建 chat 模型的 messages，支持 {content} 占位符"""
        resolved, content_embedded = self._resolve_prompt(prompt, input_data)
        if content_embedded:
            return [{"role": "user", "content": resolved}]

        formatted = self._format_input_data(input_data)
        clean_prompt = resolved.replace('{content}', '').rstrip()
        if formatted:
            if clean_prompt:
                return [
                    {"role": "system", "content": clean_prompt},
                    {"role": "user", "content": formatted},
                ]
            return [{"role": "user", "content": formatted}]

        return [{"role": "user", "content": clean_prompt}]

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
            messages = self._build_chat_messages(prompt, input_data)

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
            messages = self._build_chat_messages(prompt, input_data)

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
            messages = self._build_chat_messages(prompt, input_data)
            
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
            messages = self._build_chat_messages(prompt, input_data)

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

class DeepSeekProvider(LLMProvider):
    """DeepSeek 大模型提供商（OpenAI 兼容接口），使用 V4 系列模型"""

    def __init__(self, api_key: str, model_name: str = "deepseek-v4-flash", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        try:
            import openai
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1"
            )
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用 DeepSeek API（OpenAI 兼容接口）"""
        try:
            messages = self._build_chat_messages(prompt, input_data)

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
            logger.error(f"DeepSeek调用失败: {str(e)}")
            raise

    def test_connection(self) -> bool:
        """测试 DeepSeek 连接"""
        try:
            response = self.call("请回复'测试成功'")
            return "测试成功" in response.content or "success" in response.content.lower()
        except Exception as e:
            logger.error(f"DeepSeek连接测试失败: {e}")
            return False

    @staticmethod
    def get_available_models() -> List[ModelInfo]:
        """获取 DeepSeek 可用模型（V4 系列）"""
        return [
            ModelInfo(
                name="deepseek-v4-flash",
                display_name="DeepSeek V4 Flash",
                provider=ProviderType.DEEPSEEK,
                max_tokens=1_000_000,
                description="DeepSeek V4标准版，1M上下文，性价比极高"
            ),
            ModelInfo(
                name="deepseek-v4-pro",
                display_name="DeepSeek V4 Pro",
                provider=ProviderType.DEEPSEEK,
                max_tokens=1_000_000,
                description="DeepSeek V4旗舰版，1M上下文，最强性能"
            ),
        ]


class MoarkProvider(LLMProvider):
    """模力方舟（Gitee AI）大模型提供商（OpenAI 兼容接口）"""

    def __init__(self, api_key: str, model_name: str = "deepseek-ai/DeepSeek-V4-Flash", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        try:
            import openai
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url="https://ai.gitee.com/v1"
            )
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用模力方舟 API（OpenAI 兼容接口）"""
        try:
            messages = self._build_chat_messages(prompt, input_data)

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
            logger.error(f"模力方舟调用失败: {str(e)}")
            raise

    def test_connection(self) -> bool:
        """测试模力方舟连接"""
        try:
            response = self.call("请回复'测试成功'")
            return "测试成功" in response.content or "success" in response.content.lower()
        except Exception as e:
            logger.error(f"模力方舟连接测试失败: {e}")
            return False

    @staticmethod
    def get_available_models() -> List[ModelInfo]:
        """获取模力方舟可用模型"""
        return [
            ModelInfo(
                name="deepseek-ai/DeepSeek-V4-Flash",
                display_name="DeepSeek V4 Flash",
                provider=ProviderType.MOARK,
                max_tokens=1_000_000,
                description="模力方舟 DeepSeek V4 Flash，1M上下文"
            ),
            ModelInfo(
                name="deepseek-ai/DeepSeek-V4-Pro",
                display_name="DeepSeek V4 Pro",
                provider=ProviderType.MOARK,
                max_tokens=1_000_000,
                description="模力方舟 DeepSeek V4 Pro，最强性能"
            ),
            ModelInfo(
                name="Qwen3-8B",
                display_name="Qwen3-8B (免费)",
                provider=ProviderType.MOARK,
                max_tokens=32768,
                description="模力方舟 Qwen3-8B，阿里通义千问3，免费模型"
            ),
            ModelInfo(
                name="InternLM3-8B-Instruct",
                display_name="InternLM3-8B (免费)",
                provider=ProviderType.MOARK,
                max_tokens=32768,
                description="模力方舟 InternLM3-8B，书生·浦语3，免费模型"
            ),
            ModelInfo(
                name="Qwen/Qwen2.5-72B-Instruct",
                display_name="Qwen2.5-72B",
                provider=ProviderType.MOARK,
                max_tokens=131072,
                description="模力方舟 Qwen2.5-72B，阿里通义千问"
            ),
            ModelInfo(
                name="meta-llama/Meta-Llama-3.1-70B-Instruct",
                display_name="Llama 3.1 70B",
                provider=ProviderType.MOARK,
                max_tokens=131072,
                description="模力方舟 Llama 3.1 70B"
            ),
        ]


class OllamaProvider(LLMProvider):
    """本地Ollama大模型提供商（OpenAI 兼容接口）"""

    SAFETY_MARGIN_TOKENS = 2000

    def __init__(self, api_key: str, model_name: str = "qwen2.5", base_url: str = "http://localhost:11434/v1", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        self.base_url = base_url
        self._warmed_up = False
        self._truncated_prompt = None
        self.context_window = kwargs.get('context_window', 16384)
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

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 2.0 + other_chars * 0.3)

    def _truncate_input_if_needed(self, prompt: str, input_data: Any) -> Any:
        """如果总输入超出上下文窗口，截断 input_data 以适配"""
        if input_data is None or not isinstance(input_data, str):
            return input_data
        input_text = prompt + input_data
        estimated_input = self._estimate_tokens(input_text)
        max_input_tokens = self.context_window - self.SAFETY_MARGIN_TOKENS
        if estimated_input <= max_input_tokens:
            return input_data
        prompt_tokens = self._estimate_tokens(prompt)
        input_data_tokens = estimated_input - prompt_tokens
        max_data_tokens = max_input_tokens - prompt_tokens
        if max_data_tokens <= 64:
            logger.warning(
                f"提示词({prompt_tokens}t)本身已接近上下文窗口({self.context_window}), "
                f"无法为输入数据预留空间"
            )
            return input_data
        ratio = max_data_tokens / input_data_tokens
        keep_chars = int(len(input_data) * ratio)
        truncated = input_data[:max(keep_chars, 200)]
        logger.warning(
            f"本地模型上下文窗口不足: 预估输入 {estimated_input}t > {max_input_tokens}t, "
            f"input_data 已从 {len(input_data)} 截断至 {len(truncated)} 字符({ratio:.0%})"
        )
        return truncated

    def _parse_actual_context(self, error_msg: str) -> Optional[int]:
        """从错误信息中解析本地模型的实际上下文窗口大小"""
        import re
        match = re.search(r'n_ctx:\s*(\d+)', error_msg)
        if match:
            return int(match.group(1))
        return None

    def _truncate_input_for_retry(self, prompt: str, input_data: Any) -> str:
        self._truncated_prompt = None
        prompt_est = self._estimate_tokens(prompt)
        max_keep = self.context_window - self.SAFETY_MARGIN_TOKENS

        if prompt_est >= max_keep:
            budget = max(64, max_keep - 50)
            ratio = budget / max(prompt_est, 1)
            keep_chars = int(len(prompt) * ratio)
            self._truncated_prompt = prompt[:max(keep_chars, 200)]
            logger.warning(
                f"提示词({prompt_est}t)超过上下文预算({max_keep}t)，"
                f"已截断至 {self._estimate_tokens(self._truncated_prompt)}t"
            )
            return ""

        if input_data and isinstance(input_data, str):
            data_budget = max_keep - prompt_est
            data_ratio = data_budget / max(self._estimate_tokens(input_data), 1)
            keep_chars = int(len(input_data) * min(data_ratio, 1.0))
            return input_data[:max(keep_chars, 100)]
        return ""

    def _adjust_max_tokens(self, user_max_tokens: Optional[int], prompt: str, input_data: Any) -> int:
        input_text = prompt
        if input_data:
            if isinstance(input_data, str):
                input_text += input_data
            else:
                input_text += str(input_data)
        estimated_input = self._estimate_tokens(input_text)
        available = self.context_window - estimated_input - self.SAFETY_MARGIN_TOKENS
        if user_max_tokens is not None:
            capped = min(user_max_tokens, available)
        else:
            capped = available
        capped = max(capped, 64)
        if capped < (user_max_tokens or 0):
            logger.info(
                f"Ollama max_tokens 已从 {user_max_tokens} 裁剪至 {capped} "
                f"(预估输入 {estimated_input} tokens, 上下文 {self.context_window})"
            )
        return capped

    def _detect_context_window(self):
        probe_text = "test context window probe padding " * 500
        try:
            self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": probe_text}],
                max_tokens=1,
                temperature=0,
                timeout=30.0
            )
            if self.context_window < 16384:
                self.context_window = 16384
            logger.info(f"Ollama 上下文窗口探针通过(>=4K), 当前设定: {self.context_window}")
        except Exception as e:
            actual_ctx = self._parse_actual_context(str(e))
            if actual_ctx:
                self.context_window = actual_ctx
                logger.warning(
                    f"Ollama 模型实际上下文窗口为 {self.context_window}, "
                    f"已在初始化时自动适配"
                )
            else:
                logger.debug(f"上下文检测非超限错误(不影响): {e}")

    def _warmup(self):
        if self._warmed_up:
            return
        logger.info("Ollama 模型预热中...")
        try:
            self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
                temperature=0,
                timeout=120.0
            )
            self._warmed_up = True
            self._detect_context_window()
            logger.info(f"Ollama 模型预热完成，上下文窗口: {self.context_window}")
        except Exception as e:
            logger.warning(f"Ollama 模型预热失败: {e}")
            self._warmed_up = True

    def warmup(self):
        self._warmup()

    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用Ollama API（OpenAI兼容接口）"""
        try:
            self.warmup()
            input_data = self._truncate_input_if_needed(prompt, input_data)
            messages = self._build_chat_messages(prompt, input_data)

            kwargs = dict(kwargs)
            kwargs['max_tokens'] = self._adjust_max_tokens(
                kwargs.get('max_tokens'), prompt, input_data
            )

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
            error_msg = str(e)
            if "model reloaded" in error_msg.lower():
                logger.warning(f"LM Studio模型正在重新加载，等待3秒后自动重试: {error_msg}")
                import time
                time.sleep(3)
                try:
                    retry_response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        **kwargs
                    )
                    retry_content = retry_response.choices[0].message.content
                    logger.info(f"LM Studio模型重载后重试成功")
                    return LLMResponse(
                        content=retry_content,
                        usage={
                            "prompt_tokens": retry_response.usage.prompt_tokens,
                            "completion_tokens": retry_response.usage.completion_tokens,
                            "total_tokens": retry_response.usage.total_tokens
                        } if retry_response.usage else None,
                        model=self.model_name,
                        finish_reason=retry_response.choices[0].finish_reason
                    )
                except Exception as retry_e:
                    logger.error(f"LM Studio模型重载后重试仍然失败: {retry_e}")
                    raise
            if any(kw in error_msg.lower() for kw in ["context size", "context_length", "maximum context", "context length", "n_ctx"]):
                actual_ctx = self._parse_actual_context(error_msg)
                if actual_ctx:
                    logger.warning(
                        f"本地模型实际上下文窗口为 {actual_ctx}, 低于默认值 {self.context_window}, "
                        f"已自动适配为 {actual_ctx}。建议在LM Studio中加载模型时增大Context Length"
                    )
                    self.context_window = actual_ctx
                logger.warning(f"本地模型上下文超限，尝试截断后重试: {error_msg}")
                try:
                    truncated_input = self._truncate_input_for_retry(prompt, input_data)
                    retry_prompt = self._truncated_prompt if self._truncated_prompt else prompt
                    retry_messages = self._build_chat_messages(retry_prompt, truncated_input)
                    retry_kwargs = dict(kwargs)
                    retry_kwargs['max_tokens'] = min(kwargs.get('max_tokens', 4096), 1024)
                    retry_response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=retry_messages,
                        **retry_kwargs
                    )
                    retry_content = retry_response.choices[0].message.content
                    logger.info(f"上下文超限重试成功")
                    return LLMResponse(
                        content=retry_content,
                        usage={
                            "prompt_tokens": retry_response.usage.prompt_tokens,
                            "completion_tokens": retry_response.usage.completion_tokens,
                            "total_tokens": retry_response.usage.total_tokens
                        } if retry_response.usage else None,
                        model=self.model_name,
                        finish_reason=retry_response.choices[0].finish_reason
                    )
                except Exception as retry_e:
                    logger.error(
                        f"模型上下文({self.context_window})过小，无法容纳提示词({self._estimate_tokens(prompt)}t)。"
                        f"请在LM Studio中加载模型时增大Context Length设置，或使用更大上下文的模型"
                    )
                    raise
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

    SAFETY_MARGIN_TOKENS = 2000

    def __init__(self, api_key: str, model_name: str = "qwen2.5-7b-instruct", base_url: str = "http://localhost:1234/v1", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        self.base_url = base_url
        self._warmed_up = False
        self._truncated_prompt = None
        self.context_window = kwargs.get('context_window', 16384)
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

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 2.0 + other_chars * 0.3)

    def _truncate_input_if_needed(self, prompt: str, input_data: Any) -> Any:
        """如果总输入超出上下文窗口，截断 input_data 以适配"""
        if input_data is None or not isinstance(input_data, str):
            return input_data
        input_text = prompt + input_data
        estimated_input = self._estimate_tokens(input_text)
        max_input_tokens = self.context_window - self.SAFETY_MARGIN_TOKENS
        if estimated_input <= max_input_tokens:
            return input_data
        prompt_tokens = self._estimate_tokens(prompt)
        input_data_tokens = estimated_input - prompt_tokens
        max_data_tokens = max_input_tokens - prompt_tokens
        if max_data_tokens <= 64:
            logger.warning(
                f"提示词({prompt_tokens}t)本身已接近上下文窗口({self.context_window}), "
                f"无法为输入数据预留空间"
            )
            return input_data
        ratio = max_data_tokens / input_data_tokens
        keep_chars = int(len(input_data) * ratio)
        truncated = input_data[:max(keep_chars, 200)]
        logger.warning(
            f"本地模型上下文窗口不足: 预估输入 {estimated_input}t > {max_input_tokens}t, "
            f"input_data 已从 {len(input_data)} 截断至 {len(truncated)} 字符({ratio:.0%})"
        )
        return truncated

    def _parse_actual_context(self, error_msg: str) -> Optional[int]:
        """从错误信息中解析本地模型的实际上下文窗口大小"""
        import re
        match = re.search(r'n_ctx:\s*(\d+)', error_msg)
        if match:
            return int(match.group(1))
        return None

    def _truncate_input_for_retry(self, prompt: str, input_data: Any) -> str:
        self._truncated_prompt = None
        prompt_est = self._estimate_tokens(prompt)
        max_keep = self.context_window - self.SAFETY_MARGIN_TOKENS

        if prompt_est >= max_keep:
            budget = max(64, max_keep - 50)
            ratio = budget / max(prompt_est, 1)
            keep_chars = int(len(prompt) * ratio)
            self._truncated_prompt = prompt[:max(keep_chars, 200)]
            logger.warning(
                f"提示词({prompt_est}t)超过上下文预算({max_keep}t)，"
                f"已截断至 {self._estimate_tokens(self._truncated_prompt)}t"
            )
            return ""

        if input_data and isinstance(input_data, str):
            data_budget = max_keep - prompt_est
            data_ratio = data_budget / max(self._estimate_tokens(input_data), 1)
            keep_chars = int(len(input_data) * min(data_ratio, 1.0))
            return input_data[:max(keep_chars, 100)]
        return ""

    def _adjust_max_tokens(self, user_max_tokens: Optional[int], prompt: str, input_data: Any) -> int:
        input_text = prompt
        if input_data:
            if isinstance(input_data, str):
                input_text += input_data
            else:
                input_text += str(input_data)
        estimated_input = self._estimate_tokens(input_text)
        available = self.context_window - estimated_input - self.SAFETY_MARGIN_TOKENS
        if user_max_tokens is not None:
            capped = min(user_max_tokens, available)
        else:
            capped = available
        capped = max(capped, 64)
        if capped < (user_max_tokens or 0):
            logger.info(
                f"LM Studio max_tokens 已从 {user_max_tokens} 裁剪至 {capped} "
                f"(预估输入 {estimated_input} tokens, 上下文 {self.context_window})"
            )
        return capped

    def _detect_context_window(self):
        probe_text = "test context window probe padding " * 500
        try:
            self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": probe_text}],
                max_tokens=1,
                temperature=0,
                timeout=30.0
            )
            if self.context_window < 16384:
                self.context_window = 16384
            logger.info(f"LM Studio 上下文窗口探针通过(>=4K), 当前设定: {self.context_window}")
        except Exception as e:
            actual_ctx = self._parse_actual_context(str(e))
            if actual_ctx:
                self.context_window = actual_ctx
                logger.warning(
                    f"LM Studio 模型实际上下文窗口为 {self.context_window}, "
                    f"已在初始化时自动适配"
                )
            else:
                logger.debug(f"上下文检测非超限错误(不影响): {e}")

    def _warmup(self):
        if self._warmed_up:
            return
        logger.info("LM Studio 模型预热中...")
        try:
            self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
                temperature=0,
                timeout=120.0
            )
            self._warmed_up = True
            self._detect_context_window()
            logger.info(f"LM Studio 模型预热完成，上下文窗口: {self.context_window}")
        except Exception as e:
            logger.warning(f"LM Studio 模型预热失败: {e}")
            self._warmed_up = True

    def warmup(self):
        self._warmup()

    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用LM Studio API（OpenAI兼容接口）"""
        try:
            self.warmup()
            input_data = self._truncate_input_if_needed(prompt, input_data)
            messages = self._build_chat_messages(prompt, input_data)

            kwargs = dict(kwargs)
            kwargs['max_tokens'] = self._adjust_max_tokens(
                kwargs.get('max_tokens'), prompt, input_data
            )

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
            error_msg = str(e)
            if "model reloaded" in error_msg.lower():
                logger.warning(f"LM Studio模型正在重新加载，等待3秒后自动重试: {error_msg}")
                import time
                time.sleep(3)
                try:
                    retry_response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        **kwargs
                    )
                    retry_content = retry_response.choices[0].message.content
                    logger.info(f"LM Studio模型重载后重试成功")
                    return LLMResponse(
                        content=retry_content,
                        usage={
                            "prompt_tokens": retry_response.usage.prompt_tokens,
                            "completion_tokens": retry_response.usage.completion_tokens,
                            "total_tokens": retry_response.usage.total_tokens
                        } if retry_response.usage else None,
                        model=self.model_name,
                        finish_reason=retry_response.choices[0].finish_reason
                    )
                except Exception as retry_e:
                    logger.error(f"LM Studio模型重载后重试仍然失败: {retry_e}")
                    raise
            if any(kw in error_msg.lower() for kw in ["context size", "context_length", "maximum context", "context length", "n_ctx"]):
                actual_ctx = self._parse_actual_context(error_msg)
                if actual_ctx:
                    logger.warning(
                        f"本地模型实际上下文窗口为 {actual_ctx}, 低于默认值 {self.context_window}, "
                        f"已自动适配为 {actual_ctx}。建议在LM Studio中加载模型时增大Context Length"
                    )
                    self.context_window = actual_ctx
                logger.warning(f"LM Studio上下文超限，尝试截断后重试: {error_msg}")
                try:
                    truncated_input = self._truncate_input_for_retry(prompt, input_data)
                    retry_prompt = self._truncated_prompt if self._truncated_prompt else prompt
                    retry_messages = self._build_chat_messages(retry_prompt, truncated_input)
                    retry_kwargs = dict(kwargs)
                    retry_kwargs['max_tokens'] = min(kwargs.get('max_tokens', 4096), 1024)
                    retry_response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=retry_messages,
                        **retry_kwargs
                    )
                    retry_content = retry_response.choices[0].message.content
                    logger.info(f"LM Studio上下文超限重试成功")
                    return LLMResponse(
                        content=retry_content,
                        usage={
                            "prompt_tokens": retry_response.usage.prompt_tokens,
                            "completion_tokens": retry_response.usage.completion_tokens,
                            "total_tokens": retry_response.usage.total_tokens
                        } if retry_response.usage else None,
                        model=self.model_name,
                        finish_reason=retry_response.choices[0].finish_reason
                    )
                except Exception as retry_e:
                    logger.error(
                        f"模型上下文({self.context_window})过小，无法容纳提示词({self._estimate_tokens(prompt)}t)。"
                        f"请在LM Studio中加载模型时增大Context Length设置，或使用更大上下文的模型"
                    )
                    raise
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
        ProviderType.DEEPSEEK: DeepSeekProvider,
        ProviderType.MOARK: MoarkProvider,
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
