"""
统一的LLM重试管理器

解决P0问题#2：LLM重试机制不完善
实现统一的重试策略、缓存机制和降级回退
"""

import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class LLMRetryManager:
    """
    LLM重试管理器
    统一处理LLM调用的重试、缓存和降级
    """

    def __init__(self, max_retries: int = 3, cache_dir: Optional[Path] = None):
        self.max_retries = max_retries
        self.cache_dir = cache_dir
        self._init_cache_dir()

    def _init_cache_dir(self):
        """初始化缓存目录"""
        if self.cache_dir is None:
            self.cache_dir = Path(__file__).parent / "llm_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def call_with_retry(
        self,
        call_func: Callable,
        prompt: str,
        input_data: Dict[str, Any],
        step_name: str,
        chunk_index: int,
        cache_enabled: bool = True,
        **kwargs
    ):
        """
        带重试机制的LLM调用
        
        Args:
            call_func: LLM调用函数
            prompt: 提示词
            input_data: 输入数据
            step_name: 步骤名称（用于缓存文件命名）
            chunk_index: 块索引（用于缓存文件命名）
            cache_enabled: 是否启用缓存
            **kwargs: 其他参数
            
        Returns:
            LLM响应或降级结果
        """
        cache_key = self._build_cache_key(step_name, chunk_index)
        cached_result = None
        
        # 检查缓存
        if cache_enabled:
            cached_result = self._get_cache(cache_key)
            if cached_result:
                logger.info(f"使用缓存结果: {step_name} chunk {chunk_index}")
                return cached_result
        
        # 执行带重试的调用
        last_error = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"LLM调用尝试 {attempt}/{self.max_retries}: {step_name} chunk {chunk_index}")
                
                # 调用函数
                response = call_func(prompt, input_data, **kwargs)
                
                if response:
                    # 成功，保存到缓存
                    if cache_enabled:
                        self._save_cache(cache_key, response)
                    
                    return response
                    
            except Exception as e:
                last_error = e
                logger.error(f"LLM调用失败 (尝试 {attempt}/{self.max_retries}): {e}")
                
                # 保存失败的调用以便调试
                self._save_failed_call(cache_key, attempt, str(e), input_data)
                
                # 最后一次失败，不重试
                if attempt == self.max_retries:
                    break
                
                # 短暂延迟后重试
                time.sleep(attempt * 0.5)  # 线性递增延迟
        
        # 所有重试都失败，返回降级结果
        logger.warning(f"所有LLM重试失败: {step_name} chunk {chunk_index}")
        raise LLMCallFailedException(
            f"{step_name} chunk {chunk_index} 所有重试都失败了",
            last_error=last_error,
            step_name=step_name,
            chunk_index=chunk_index
        )

    def _build_cache_key(self, step_name: str, chunk_index: int) -> str:
        """构建缓存键"""
        return f"{step_name}_chunk_{chunk_index}.json"

    def _get_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存结果"""
        cache_path = self.cache_dir / cache_key
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查缓存是否为失败缓存
            if data.get("is_failed", False):
                return None
            
            return data.get("response")
        except (json.JSONDecodeError, KeyError):
            logger.warning(f"缓存文件损坏，忽略: {cache_key}")
            return None

    def _save_cache(self, cache_key: str, response: Dict[str, Any]):
        """保存缓存结果"""
        cache_path = self.cache_dir / cache_key
        data = {
            "response": response,
            "timestamp": "",
            "is_failed": False
        }
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"缓存保存失败: {e}")

    def _save_failed_call(self, cache_key: str, attempt: int, error: str, input_data: Dict[str, Any]):
        """保存失败调用记录"""
        failed_path = self.cache_dir / f"{cache_key}_attempt_{attempt}_failed.json"
        data = {
            "is_failed": True,
            "attempt": attempt,
            "error": error,
            "input": input_data,
            "timestamp": ""
        }
        try:
            with open(failed_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"失败记录保存失败: {e}")



    """
    class降级策略管理器:
    降级策略管理器
    管理LLM不可用时的降级策略
    """

    def __init__(self):
        self.strategies = {}
        self._init_default_strategies()

    def _init_default_strategies(self):
        """初始化默认降级策略"""
        self.register_strategy("timeline", self._timeline_fallback)
        self.register_strategy("scoring", self._scoring_fallback)
        self.register_strategy("title", self._title_fallback)
        self.register_strategy("clustering", self._clustering_fallback)

    def register_strategy(self, name: str, strategy_func: Callable):
        """注册降级策略"""
        self.strategies[name] = strategy_func

    def get_fallback(self, step_name: str) -> Optional[Callable]:
        """获取指定步骤的降级策略"""
        return self.strategies.get(step_name)

    def _timeline_fallback(self, input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """时间线提取的降级：直接返回时间范围，不做LLM分析"""
        # 简单返回开始和结束时间作为fallback
        srt_data = input_data.get("srt_data", [])
        fallback_timeline = []
        
        if srt_data:
            # 将整个视频作为一个大段落
            fallback_timeline.append({
                "outline": "完整视频内容",
                "start_time": srt_data[0].get("start_time", "00:00:00"),
                "end_time": srt_data[-1].get("end_time", "00:00:00")
            })
        
        return fallback_timeline

    def _scoring_fallback(self, timeline_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """评分的降级：基于内容长度简单评分"""
        scored_clips = []
        
        for item in timeline_data:
            # 基于内容长度评分（30-120秒为最佳）
            duration = item.get("duration", 60)
            if 30 <= duration <= 120:
                score = 7.0 + (1.0 - abs(duration - 60) / 60) * 2.0
            elif duration < 30:
                score = 5.0 + (duration / 30) * 2.0
            else:
                score = 6.0 - min((duration - 120) / 120, 0.5)
            
            scored_clips.append({
                **item,
                "score": round(score, 2),
                "final_score": round(score, 2),
                "score_source": "fallback_duration_based"
            })
        
        return scored_clips

    def _title_fallback(self, timeline_item: Dict[str, Any]) -> str:
        """标题生成的降级：使用outline或前30字"""
        outline = timeline_item.get("outline", "")
        
        if isinstance(outline, dict):
            return outline.get("title", "") or outline.get("content", "")
        elif isinstance(outline, str) and outline:
            return outline[:50]
        
        return "精彩片段"

    def _clustering_fallback(self, timeline_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """聚类的降级：按顺序分组，每3个一组"""
        clusters = []
        current_cluster = []
        
        for i, item in enumerate(timeline_data):
            current_cluster.append(item)
            
            if len(current_cluster) >= 3 or i == len(timeline_data) - 1:
                clusters.append({
                    "id": str(len(clusters)),
                    "collection_title": f"精彩合集 {len(clusters) + 1}",
                    "description": "自动聚类结果",
                    "clips": current_cluster.copy()
                })
                current_cluster = []
        
        return clusters
