"""
LLM客户端 - 简化为仅用于占位
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class LLMClient:
    """简化的LLM客户端"""

    def __init__(self, provider: str = "zhipu", model: str = "glm-4"):
        self.provider = provider
        self.model = model
        self.max_retries = 3
        self.retry_delay = 1
        logger.info(f"LLMClient初始化 (provider={provider}, model={model})")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """生成文本"""
        logger.warning("LLMClient.generate 被调用但未实现，返回空字符串")
        return ""

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """生成JSON格式响应"""
        logger.warning("LLMClient.generate_json 被调用但未实现，返回空字典")
        return {}

    def call_with_retry(self, prompt_template: str, input_data: Dict[str, Any], max_retries: int = 3) -> Optional[str]:
        """
        带重试的LLM调用

        Args:
            prompt_template: 提示模板
            input_data: 输入数据
            max_retries: 最大重试次数

        Returns:
            LLM响应字符串，失败返回None
        """
        logger.warning("LLMClient.call_with_retry 被调用但未实现，返回None")
        return None

    def set_temperature(self, temperature: float):
        """设置温度参数"""
        self.temperature = temperature

    def set_max_tokens(self, max_tokens: int):
        """设置最大token数"""
        self.max_tokens = max_tokens
