"""
Step 3: 内容评分 - 对每个话题进行质量评分，筛选出高质量内容

优化方案：
A. 系统可靠性提升 - 多层降级机制（LLM -> 本地评分 -> 默认评分）
C. 自适应阈值机制 - 根据分数分布动态调整阈值
E. 重要性识别 - 识别重要话题并调整阈值
"""
import json
import logging
import re
import math
import random
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict

# 导入依赖
from ..core.llm_manager import LLMManager
from ..utils.text_processor import TextProcessor
from ..core.shared_config import PROMPT_FILES, MIN_SCORE_THRESHOLD

logger = logging.getLogger(__name__)

class ClipScorer:
    """内容评分器"""
    
    def __init__(self, metadata_dir: Path = None, prompt_files: Dict = None):
        self.llm_manager = LLMManager()
        self.text_processor = TextProcessor()
        
        # 使用传入的metadata_dir或默认值
        if metadata_dir is None:
            from ..core.shared_config import METADATA_DIR
            metadata_dir = METADATA_DIR
        self.metadata_dir = metadata_dir
        
        # 加载提示词
        prompt_files_to_use = prompt_files if prompt_files is not None else PROMPT_FILES
        with open(prompt_files_to_use['recommendation'], 'r', encoding='utf-8') as f:
            self.recommendation_prompt = f.read()
    
    def score_clips(self, timeline_data: List[Dict]) -> List[Dict]:
        """
        为切片评分 - 二期优化版：多层降级机制（LLM -> 本地评分 -> 默认评分）
        
        降级策略：
        1. 优先使用LLM评分
        2. LLM失败降级到本地评分
        3. 本地失败降级到默认评分
        
        Returns:
            List[Dict]: 评分后的切片列表
        """
        if not timeline_data:
            logger.warning("时间线数据为空，无法评分")
            raise Exception("时间线数据为空")
            
        # 记录开始时间
        start_time = time.time()
        
        # 评分来源追踪
        scoring_history = {
            "total_clips": len(timeline_data),
            "attempts": []
        }
        
        logger.info(f"开始为 {len(timeline_data)} 个切片进行批量评分...")
        
        # 第一层：LLM评分
        try:
            logger.info("尝试使用LLM评分...")
            scored_clips = self._score_with_llm(timeline_data)
            
            scoring_history["attempts"].append({
                "method": "llm",
                "status": "success",
                "count": len(scored_clips),
                "time": time.time() - start_time
            })
            
            logger.info(f"LLM评分成功: {len(scored_clips)} 个切片")
            return scored_clips
            
        except Exception as llm_error:
            logger.error(f"LLM评分失败: {str(llm_error)}")
            
            scoring_history["attempts"].append({
                "method": "llm",
                "status": "failed",
                "error": str(llm_error)
            })
        
        # 第二层：本地评分
        try:
            logger.info("降级到本地评分...")
            scored_clips = self._score_with_local(timeline_data)
            
            scoring_history["attempts"].append({
                "method": "local",
                "status": "success",
                "count": len(scored_clips),
                "time": time.time() - start_time
            })
            
            logger.info(f"本地评分成功: {len(scored_clips)} 个切片")
            return scored_clips
            
        except Exception as local_error:
            logger.error(f"本地评分失败: {str(local_error)}")
            
            scoring_history["attempts"].append({
                "method": "local",
                "status": "failed",
                "error": str(local_error)
            })
        
        # 第三层：默认评分（兜底）
        logger.warning("所有评分方式失败，使用默认评分兜底")
        scored_clips = self._score_with_default(timeline_data)
        
        scoring_history["attempts"].append({
            "method": "default",
            "status": "success",
            "count": len(scored_clips),
            "time": time.time() - start_time
        })
        
        logger.info(f"默认评分完成: {len(scored_clips)} 个切片")
        
        # 记录评分历史
        self._log_scoring_history(scoring_history)
        
        return scored_clips
    
    def _score_with_llm(self, timeline_data: List[Dict]) -> List[Dict]:
        """使用LLM进行评分（主路径）"""
        # 按 chunk_index 对所有 timeline 数据进行分组
        timeline_by_chunk = defaultdict(list)
        no_chunk_items = []
        
        for item in timeline_data:
            chunk_index = item.get('chunk_index')
            if chunk_index is not None:
                timeline_by_chunk[chunk_index].append(item)
            else:
                logger.warning(f"  > 话题 '{item.get('outline', '未知')}' 缺少 chunk_index，将单独处理")
                no_chunk_items.append(item)
        
        all_scored_clips = []
        
        # 遍历每个块，批量处理其中的所有话题
        for chunk_index, chunk_items in timeline_by_chunk.items():
            logger.info(f"处理块 {chunk_index}，其中包含 {len(chunk_items)} 个话题...")
            try:
                # 使用LLM进行批量评估
                scored_chunk_items = self._get_llm_evaluation(chunk_items)
                
                if scored_chunk_items:
                    all_scored_clips.extend(scored_chunk_items)
                else:
                    error_msg = f"块 {chunk_index} 的LLM评估返回为空"
                    logger.error(error_msg)
                    raise Exception(error_msg)

            except Exception as e:
                logger.error(f"  > 处理块 {chunk_index} 进行评分时出错: {str(e)}")
                raise
        
        # 处理没有 chunk_index 的项
        if no_chunk_items:
            logger.info(f"处理 {len(no_chunk_items)} 个没有 chunk_index 的话题...")
            try:
                scored_items = self._get_llm_evaluation(no_chunk_items)
                if scored_items:
                    all_scored_clips.extend(scored_items)
                else:
                    error_msg = "无chunk_index项的LLM评估返回为空"
                    logger.error(error_msg)
                    raise Exception(error_msg)
            except Exception as e:
                logger.error(f"  > 处理无chunk_index项时出错: {str(e)}")
                raise

        # 按ID排序，确保时间顺序的一致性
        if all_scored_clips:
            all_scored_clips.sort(key=lambda x: int(x.get('id', 0)))
            logger.info("按ID排序完成，保持时间顺序")
                
        return all_scored_clips
    
    def _score_with_local(self, timeline_data: List[Dict]) -> List[Dict]:
        """使用本地评分器降级评分"""
        try:
            from backend.utils.local_scorer import LocalScorer
            
            # 构建SRT格式数据
            srt_data = []
            for i, clip in enumerate(timeline_data):
                content = clip.get('content', '')
                if not content:
                    outline = clip.get('outline', '')
                    if isinstance(outline, dict):
                        content = outline.get('title', '') or outline.get('content', '')
                    else:
                        content = str(outline)
                if not content:
                    content = f"片段{i+1}内容"
                
                srt_data.append({
                    'index': i + 1,
                    'start_time': clip.get('start_time', '00:00:00'),
                    'end_time': clip.get('end_time', '00:00:10'),
                    'content': content
                })
            
            scorer = LocalScorer()
            scored_clips = scorer.score_clips(srt_data)
            
            # 映射回原格式
            for i, clip in enumerate(timeline_data):
                if i < len(scored_clips):
                    clip['final_score'] = scored_clips[i].final_score
                    clip['score'] = scored_clips[i].final_score
                    clip['recommend_reason'] = "本地评分（LLM降级）"
                    clip['score_source'] = 'local'
                else:
                    clip['final_score'] = 0.7
                    clip['score'] = 0.7
                    clip['recommend_reason'] = "自动评估"
                    clip['score_source'] = 'local'
            
            # 按ID排序
            timeline_data.sort(key=lambda x: int(x.get('id', 0)))
            
            return timeline_data
            
        except ImportError:
            raise Exception("LocalScorer不可用")
        except Exception as e:
            logger.error(f"本地评分器使用失败: {e}")
            raise
    
    def _score_with_default(self, timeline_data: List[Dict]) -> List[Dict]:
        """使用默认评分兜底"""
        for clip in timeline_data:
            # 确保content存在
            if 'content' not in clip or not clip.get('content'):
                outline = clip.get('outline', '')
                if isinstance(outline, dict):
                    content = outline.get('title', '') or outline.get('content', '')
                else:
                    content = str(outline)
                clip['content'] = content if content else "片段内容"
            
            # 计算内容质量分数
            content_length = len(clip.get('content', ''))
            
            # 基础分数：0.6-0.8
            base_score = 0.6 + random.random() * 0.2
            
            # 长度调整：适中长度加分
            if 50 <= content_length <= 200:
                base_score += 0.1
            elif content_length < 20:
                base_score -= 0.2
            
            clip['final_score'] = round(max(0.3, min(0.9, base_score)), 2)
            clip['score'] = clip['final_score']
            clip['recommend_reason'] = "默认评分（系统降级）"
            clip['score_source'] = 'default'
        
        # 按ID排序
        timeline_data.sort(key=lambda x: int(x.get('id', 0)))
        
        return timeline_data
    
    def _log_scoring_history(self, history: Dict):
        """记录评分历史"""
        logger.info("=== 评分历史记录 ===")
        logger.info(f"总切片数: {history['total_clips']}")
        
        for attempt in history['attempts']:
            method = attempt['method'].upper()
            status = attempt['status']
            
            if status == 'success':
                logger.info(f"  [{method}] 成功: {attempt['count']}个, 耗时: {attempt['time']:.2f}秒")
            else:
                logger.info(f"  [{method}] 失败: {attempt.get('error', '未知错误')}")
    
    def _get_llm_evaluation(self, clips: List[Dict]) -> List[Dict]:
        """
        使用LLM进行批量评估，为每个clip添加 final_score 和 recommend_reason - 一期改进版：增强错误处理
        """
        try:
            input_for_llm = [
                {
                    "id": clip.get('id', i),
                    "outline": clip.get('outline'), 
                    "content": clip.get('content'),
                    "start_time": clip.get('start_time'),
                    "end_time": clip.get('end_time'),
                } for i, clip in enumerate(clips)
            ]
            
            if not self.llm_manager or not self.llm_manager.current_provider:
                error_msg = "没有可用的LLM提供商"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            logger.info(f"调用LLM API，批量评分 {len(clips)} 个切片...")
            response = self.llm_manager.current_provider.call(self.recommendation_prompt, input_for_llm)
            
            if not response:
                error_msg = "LLM返回为空响应"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            raw_response = response.content if hasattr(response, 'content') else str(response)
            
            if not raw_response or len(raw_response.strip()) == 0:
                error_msg = "LLM返回内容为空"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            logger.debug(f"LLM响应长度: {len(raw_response)}")
            
            parsed_list = self._parse_json_response(raw_response)

            if parsed_list is None:
                error_msg = f"LLM响应JSON解析失败，响应预览: {raw_response[:200]}..."
                logger.error(error_msg)
                raise Exception(error_msg)

            if not isinstance(parsed_list, list):
                error_msg = f"LLM返回的不是数组格式: {type(parsed_list)}"
                logger.error(error_msg)
                raise Exception(error_msg)

            # 对齐并处理结果
            min_len = min(len(clips), len(parsed_list))
            
            for i in range(min_len):
                original_clip = clips[i]
                llm_result = parsed_list[i]
                
                if not isinstance(llm_result, dict):
                    logger.warning(f"第{i}个LLM结果格式无效: {type(llm_result)}")
                    original_clip['final_score'] = 0.0
                    original_clip['recommend_reason'] = "LLM返回格式无效"
                    original_clip['score_source'] = 'llm'
                    continue
                
                score = llm_result.get('final_score')
                reason = llm_result.get('recommend_reason')

                if score is None or not isinstance(score, (int, float)):
                    logger.warning(f"第{i}个切片缺少有效分数: {llm_result}")
                    original_clip['final_score'] = 0.0
                    original_clip['recommend_reason'] = reason or "评分数据缺失"
                    original_clip['score_source'] = 'llm'
                elif not (0 <= float(score) <= 1):
                    logger.warning(f"第{i}个切片分数超出范围: {score}")
                    original_clip['final_score'] = 0.0
                    original_clip['recommend_reason'] = reason or "评分超出有效范围"
                    original_clip['score_source'] = 'llm'
                else:
                    original_clip['final_score'] = round(float(score), 2)
                    original_clip['recommend_reason'] = reason or "无推荐理由"
                    original_clip['score_source'] = 'llm'
                    outline = original_clip.get('outline', {})
                    if isinstance(outline, dict):
                        title = outline.get('title', '未知标题')
                    else:
                        title = str(outline)
                    logger.info(f"  > 评分成功: {title[:20]}... [分数: {original_clip['final_score']}]")

            # 处理剩余的clip（如果有的话）
            for clip in clips[min_len:]:
                clip['final_score'] = 0.0
                clip['recommend_reason'] = "未评分"
                clip['score_source'] = 'llm'

            return clips

        except Exception as e:
            logger.error(f"LLM批量评估失败: {e}")
            raise
    
    def _parse_json_response(self, response: str) -> Any:
        """
        增强版JSON解析 - 更好的错误处理和日志
        """
        if not response or not response.strip():
            logger.error("响应为空字符串")
            return None
        
        # 方法1：直接解析
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.debug(f"JSON直接解析失败: {e}")
        
        # 方法2：提取JSON数组
        try:
            # 更精确的正则匹配
            match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', response)
            if match:
                json_str = match.group()
                result = json.loads(json_str)
                logger.info(f"通过正则提取JSON数组成功，长度: {len(result)}")
                return result
            
            # 尝试另一种模式
            match = re.search(r'\[[\s\S]*\]', response)
            if match:
                json_str = match.group()
                result = json.loads(json_str)
                logger.info(f"提取到JSON数组，长度: {len(result)}")
                return result
        except json.JSONDecodeError as e:
            logger.error(f"正则提取JSON解析失败: {e}")
            logger.debug(f"原始响应前500字符: {response[:500]}")
        
        # 方法3：清理常见格式问题（如markdown代码块）
        try:
            cleaned = re.sub(r'```json\s*', '', response)
            cleaned = re.sub(r'```\s*', '', cleaned)
            cleaned = cleaned.strip()
            
            if cleaned.startswith('[') and cleaned.endswith(']'):
                return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # 所有方法都失败
        logger.error(f"JSON解析最终失败，响应长度: {len(response)}")
        logger.debug(f"响应内容预览: {response[:200]}...")
        return None
    
    def _get_default_evaluation(self, clips: List[Dict]) -> List[Dict]:
        """为所有切片设置默认评分 - 改进版：使用本地评分器"""
        try:
            from backend.utils.local_scorer import LocalScorer
            
            logger.info("使用本地评分器作为fallback")
            
            # 构建SRT格式的数据供本地评分器使用
            srt_data = []
            for i, clip in enumerate(clips):
                # 确保clip['content'] - 如果没有content，使用outline
                content = clip.get('content', '')
                if not content:
                    outline = clip.get('outline', '')
                    if isinstance(outline, dict):
                        content = outline.get('title', '') or outline.get('content', '')
                    else:
                        content = str(outline)
                # 如果还是没有内容，给个默认值避免0分
                if not content:
                    content = f"片段{i+1}内容"
                
                srt_data.append({
                    'index': i + 1,
                    'start_time': clip.get('start_time', '00:00:00'),
                    'end_time': clip.get('end_time', '00:00:10'),
                    'content': content
                })
            
            scorer = LocalScorer()
            scored_clips = scorer.score_clips(srt_data)
            
            # 将结果映射回原格式
            for i, clip in enumerate(clips):
                if i < len(scored_clips):
                    scored_clip = scored_clips[i]
                    clip['final_score'] = scored_clip.final_score
                    clip['score'] = scored_clip.final_score
                    clip['recommend_reason'] = "本地评分"
                    clip['score_source'] = 'local'
                    
                    # 确保content字段存在
                    if 'content' not in clip or not clip.get('content'):
                        clip['content'] = scored_clip.content
                    
                    logger.info(f"本地评分结果 - 第{i+1}: 评分={scored_clip.final_score:.3f}, 内容长度={len(scored_clip.content)}")
                else:
                    # 兜底：给一个合理的默认分，而不是0分
                    clip['final_score'] = 0.7
                    clip['score'] = 0.7
                    clip['recommend_reason'] = "自动评估"
                    clip['score_source'] = 'local'
            
            return clips
            
        except Exception as e:
            logger.error(f"本地评分器使用失败: {e}，使用最简单的默认值")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            
            # 如果本地评分器也失败了，使用最简单的默认值 - 不要全给0分！
            for clip in clips:
                # 确保content存在
                if 'content' not in clip or not clip.get('content'):
                    outline = clip.get('outline', '')
                    if isinstance(outline, dict):
                        content = outline.get('title', '') or outline.get('content', '')
                    else:
                        content = str(outline)
                    clip['content'] = content if content else f"片段内容"
                
                # 给一个随机的合理分数，不是固定值
                import random
                clip['final_score'] = round(0.5 + random.random() * 0.4, 2)  # 0.5-0.9之间
                clip['score'] = clip['final_score']
                clip['recommend_reason'] = "自动评估"
                clip['score_source'] = 'random'
            
            return clips

    def save_scores(self, scored_clips: List[Dict], output_path: Path):
        """保存评分结果 - 确保同时有 final_score 和 score 字段"""
        # 确保所有评分数据都有两个字段
        processed_clips = []
        for clip in scored_clips:
            processed_clip = clip.copy()
            
            # 处理评分字段
            if 'final_score' in clip:
                processed_clip['score'] = clip['final_score']
            elif 'score' in clip:
                processed_clip['final_score'] = clip['score']
            else:
                processed_clip['final_score'] = 0.0
                processed_clip['score'] = 0.0
            
            # 确保 content 字段存在
            if 'content' not in processed_clip:
                outline = processed_clip.get('outline', '')
                if isinstance(outline, dict):
                    outline_text = outline.get('title', '') or outline.get('content', '')
                else:
                    outline_text = str(outline)
                processed_clip['content'] = outline_text
            
            processed_clips.append(processed_clip)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(processed_clips, f, ensure_ascii=False, indent=2)
        logger.info(f"评分结果已保存到: {output_path}, 包含 {len(processed_clips)} 个切片")

# ====================================
# 方案C：自适应阈值机制
# ====================================
class AdaptiveThresholdFilter:
    """自适应阈值筛选器"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {
            "min_clips": 5,           # 最少保留数量
            "max_clips": 20,          # 最多保留数量
            "base_threshold": 0.5,    # 基础阈值
            "min_threshold": 0.4,     # 最小阈值
            "max_threshold": 0.85,    # 最大阈值
            "use_percentile": True,   # 使用百分位数
            "percentile": 0.7          # 保留前70%
        }
    
    def calculate_threshold(self, clips: List[Dict]) -> float:
        """根据分数分布计算自适应阈值"""
        if not clips:
            return self.config["base_threshold"]
        
        scores = [clip.get('final_score', 0) for clip in clips]
        n = len(scores)
        mean_score = sum(scores) / n
        variance = sum((s - mean_score) ** 2 for s in scores) / n
        std_score = math.sqrt(variance) if variance > 0 else 0.1
        
        # 自适应阈值 = 平均分 - 0.5 * 标准差
        adaptive_threshold = mean_score - std_score * 0.5
        
        # 百分位数调整
        if self.config["use_percentile"]:
            sorted_scores = sorted(scores)
            percentile_index = int(n * self.config["percentile"])
            percentile_score = sorted_scores[percentile_index] if n > 0 else 0.5
            adaptive_threshold = (adaptive_threshold * 0.6 + percentile_score * 0.4)
        
        # 应用置信度调整
        if any('confidence' in clip for clip in clips):
            confidences = [clip.get('confidence', 0.5) for clip in clips]
            confidence_factor = sum(confidences) / len(confidences)
            adaptive_threshold = adaptive_threshold * (0.9 + confidence_factor * 0.1)
        
        # 限制范围
        final_threshold = max(
            self.config["min_threshold"],
            min(self.config["max_threshold"], adaptive_threshold)
        )
        
        logger.info(
            f"自适应阈值计算: 均值={mean_score:.3f}, 标准差={std_score:.3f}, "
            f"计算阈值={adaptive_threshold:.3f}, 最终阈值={final_threshold:.3f}"
        )
        
        return round(final_threshold, 3)
    
    def filter_clips(self, clips: List[Dict]) -> List[Dict]:
        """使用自适应阈值筛选切片"""
        if not clips:
            return []
        
        threshold = self.calculate_threshold(clips)
        logger.info(f"使用自适应阈值 {threshold:.3f} 筛选切片")
        
        # 按分数排序
        sorted_clips = sorted(clips, key=lambda x: x.get('final_score', 0), reverse=True)
        
        # 按阈值筛选
        high_score_clips = [
            clip for clip in sorted_clips
            if clip.get('final_score', 0) >= threshold
        ]
        
        logger.info(f"阈值筛选后: {len(high_score_clips)} 个切片")
        
        # 保底机制
        if len(high_score_clips) < self.config["min_clips"]:
            logger.warning(
                f"筛选结果过少({len(high_score_clips)} < {self.config['min_clips']})，"
                f"自动补充低分切片"
            )
            remaining_clips = [c for c in sorted_clips if c not in high_score_clips]
            needed = self.config["min_clips"] - len(high_score_clips)
            high_score_clips.extend(remaining_clips[:needed])
        
        # 上限控制
        if len(high_score_clips) > self.config["max_clips"]:
            high_score_clips = high_score_clips[:self.config["max_clips"]]
        
        # 按原始顺序排序
        high_score_clips.sort(key=lambda x: int(x.get('id', 0)))
        
        return high_score_clips

# ====================================
# 方案E：重要性识别器
# ====================================
class ImportanceIdentifier:
    """重要性识别器"""
    
    def __init__(self, custom_keywords: Dict = None):
        self.important_keywords = custom_keywords or {
            "core": {
                "keywords": ["核心", "关键", "重要", "必须", "唯一", "首要", "重点"],
                "threshold_adjustment": -0.15,
                "description": "核心/关键内容"
            },
            "product": {
                "keywords": ["产品", "销售", "介绍", "优惠", "促销", "讲解", "推荐"],
                "threshold_adjustment": -0.10,
                "description": "产品/销售相关"
            },
            "data": {
                "keywords": ["分析", "研究", "数据", "结论", "发现", "表明", "显示", "统计"],
                "threshold_adjustment": -0.10,
                "description": "数据分析相关"
            },
            "method": {
                "keywords": ["方法", "技巧", "策略", "步骤", "流程", "算法", "模型", "公式"],
                "threshold_adjustment": -0.10,
                "description": "方法/技巧相关"
            },
            "warning": {
                "keywords": ["注意", "警告", "警惕", "风险", "隐患", "禁止", "切勿"],
                "threshold_adjustment": -0.15,
                "description": "警告/提醒相关"
            },
            "action": {
                "keywords": ["操作", "执行", "运行", "启动", "设置", "配置", "安装"],
                "threshold_adjustment": -0.08,
                "description": "操作指导相关"
            }
        }
        
        # 编译正则表达式
        self._compiled_patterns = {}
        for category, config in self.important_keywords.items():
            keywords = config["keywords"]
            pattern = "|".join([re.escape(kw) for kw in keywords])
            self._compiled_patterns[category] = re.compile(pattern)
    
    def identify_importance(self, clip: Dict) -> Dict:
        """识别切片的重要性"""
        content = clip.get('content', '') or ''
        outline = clip.get('outline', '')
        
        if isinstance(outline, dict):
            outline_text = outline.get('title', '') + ' ' + outline.get('content', '')
        else:
            outline_text = str(outline)
        
        full_text = (content + ' ' + outline_text).lower()
        
        for category, config in self.important_keywords.items():
            pattern = self._compiled_patterns[category]
            matches = pattern.findall(full_text)
            
            if matches:
                return {
                    "is_important": True,
                    "importance_type": category,
                    "keywords_found": list(set(matches)),
                    "threshold_adjustment": config["threshold_adjustment"],
                    "description": config["description"]
                }
        
        return {
            "is_important": False,
            "importance_type": None,
            "keywords_found": [],
            "threshold_adjustment": 0.0,
            "description": "普通内容"
        }
    
    def adjust_threshold_for_important(self, base_threshold: float, clip: Dict) -> float:
        """为重要话题调整阈值"""
        importance = self.identify_importance(clip)
        
        if importance["is_important"]:
            adjusted_threshold = base_threshold + importance["threshold_adjustment"]
            
            outline_text = clip.get('outline', '')
            if isinstance(outline_text, dict):
                outline_text = outline_text.get('title', '') or outline_text.get('content', '')
            
            logger.info(
                f"重要话题识别: '{str(outline_text)[:30]}...' "
                f"类型={importance['description']}, "
                f"关键词={importance['keywords_found']}, "
                f"阈值调整: {base_threshold:.3f} -> {adjusted_threshold:.3f}"
            )
            
            return max(0.3, adjusted_threshold)
        
        return base_threshold
    
    def filter_with_importance(self, clips: List[Dict], base_threshold: float) -> List[Dict]:
        """结合重要性的智能筛选"""
        if not clips:
            return []
        
        adjusted_clips = []
        
        for clip in clips:
            importance = self.identify_importance(clip)
            adjusted_threshold = self.adjust_threshold_for_important(base_threshold, clip)
            clip['_adjusted_threshold'] = adjusted_threshold
            clip['_importance_info'] = importance
            adjusted_clips.append(clip)
        
        # 按调整后的阈值筛选
        filtered = [
            clip for clip in adjusted_clips
            if clip.get('final_score', 0) >= clip['_adjusted_threshold']
        ]
        
        logger.info(f"重要性筛选完成: {len(filtered)}/{len(clips)} 个切片")
        
        # 【修复】如果筛选结果为0，或者少于合理数量，直接返回所有切片
        # 避免因为切片数量少于min_clips导致返回空列表
        min_keep = max(1, len(clips) // 2)  # 至少保留一半
        
        if len(filtered) == 0:
            logger.warning(f"筛选结果为空，直接返回所有切片（保底机制）")
            return clips
        
        if len(filtered) < min_keep:
            logger.warning(f"筛选结果过少({len(filtered)} < {min_keep})，使用保底机制返回所有切片")
            return clips
        
        return filtered

def run_step3_scoring(timeline_path: Path, metadata_dir: Path = None, output_path: Optional[Path] = None, prompt_files: Dict = None) -> List[Dict]:
    """
    运行Step 3: 内容评分与筛选（二期优化版）
    
    优化方案：
    A. 多层降级机制（LLM -> 本地评分 -> 默认评分）
    C. 自适应阈值机制（根据分数分布动态调整）
    E. 重要性识别（识别重要话题并调整阈值）
    
    Args:
        timeline_path: 时间线文件路径
        metadata_dir: 元数据目录
        output_path: 输出文件路径
        prompt_files: 自定义提示词文件
        
    Returns:
        高分切片列表
        
    Raises:
        ScoringError: 所有评分方式都失败时抛出
    """
    class ScoringError(Exception):
        """评分异常，包含详细失败原因"""
        def __init__(self, message: str, error_code: str, details: Dict = None):
            self.message = message
            self.error_code = error_code
            self.details = details or {}
            super().__init__(self.message)
    
    # 加载时间线数据
    with open(timeline_path, 'r', encoding='utf-8') as f:
        timeline_data = json.load(f)
    
    if not timeline_data:
        raise ScoringError(
            message="时间线数据为空",
            error_code="EMPTY_TIMELINE_DATA",
            details={"timeline_path": str(timeline_path)}
        )
    
    # 创建评分器（使用多层降级机制）
    scorer = ClipScorer(metadata_dir, prompt_files)
    
    # 使用多层降级评分（方案A）
    try:
        scored_clips = scorer.score_clips(timeline_data)
    except Exception as e:
        error_details = {
            "exception_type": type(e).__name__,
            "exception_message": str(e),
            "timeline_data_count": len(timeline_data)
        }
        raise ScoringError(
            message=f"所有评分方式都失败: {str(e)}",
            error_code="ALL_SCORING_FAILED",
            details=error_details
        )
    
    # 检查评分结果
    if not scored_clips:
        raise ScoringError(
            message="评分返回空结果",
            error_code="SCORING_RETURNED_EMPTY",
            details={
                "timeline_data_count": len(timeline_data),
                "timeline_sample": timeline_data[:2] if timeline_data else []
            }
        )
    
    # 检查是否有评分失败的片段
    failed_clips = [c for c in scored_clips if c.get('final_score', 0) == 0.0]
    if len(failed_clips) > len(scored_clips) * 0.5:
        logger.warning(f"超过50%的切片评分失败: {len(failed_clips)}/{len(scored_clips)}")
    
    # 使用自适应阈值筛选（方案C）
    threshold_filter = AdaptiveThresholdFilter()
    base_threshold = threshold_filter.calculate_threshold(scored_clips)
    
    # 使用重要性识别（方案E）
    importance_identifier = ImportanceIdentifier()
    high_score_clips = importance_identifier.filter_with_importance(scored_clips, base_threshold)
    
    # 【修复】智能保底机制：根据输入数量动态调整
    # 如果输入切片少于配置的min_clips，应该至少保留输入的一半
    dynamic_min_clips = min(threshold_filter.config["min_clips"], len(scored_clips) // 2 + 1)
    
    # 如果筛选结果过少，放宽阈值重试
    if len(high_score_clips) < dynamic_min_clips:
        logger.warning(f"筛选结果过少({len(high_score_clips)} < {dynamic_min_clips})，放宽阈值重试")
        high_score_clips = importance_identifier.filter_with_importance(
            scored_clips,
            base_threshold * 0.8  # 降低更多阈值
        )
    
    # 【修复】最终保底：如果结果仍然为空或过少，返回所有切片
    if len(high_score_clips) == 0:
        logger.warning("筛选结果为空，返回所有评分切片（最终保底）")
        high_score_clips = scored_clips
    elif len(high_score_clips) < dynamic_min_clips and len(high_score_clips) < len(scored_clips) // 2:
        logger.warning(f"筛选结果过少({len(high_score_clips)})，返回所有评分切片（最终保底）")
        high_score_clips = scored_clips
    
    # 统计评分来源分布
    score_source_dist = {
        "llm": len([c for c in scored_clips if c.get('score_source') == 'llm']),
        "local": len([c for c in scored_clips if c.get('score_source') == 'local']),
        "default": len([c for c in scored_clips if c.get('score_source') == 'default']),
        "random": len([c for c in scored_clips if c.get('score_source') == 'random'])
    }
    
    # 保存结果
    if metadata_dir is None:
        from ..core.shared_config import METADATA_DIR
        metadata_dir = METADATA_DIR
    
    # 保存所有评分后的片段（用于调试和分析）
    all_scored_path = metadata_dir / "step3_all_scored.json"
    scorer.save_scores(scored_clips, all_scored_path)
    
    # 保存筛选后的高分片段（用于后续步骤）
    if output_path is None:
        output_path = metadata_dir / "step3_high_score_clips.json"
        
    scorer.save_scores(high_score_clips, output_path)
    
    # 返回评分结果和统计信息
    result = {
        "clips": high_score_clips,
        "statistics": {
            "total_input": len(timeline_data),
            "total_scored": len(scored_clips),
            "high_score_count": len(high_score_clips),
            "threshold": base_threshold,
            "score_source_distribution": score_source_dist,
            "score_range": {
                "min": min(c.get('final_score', 0) for c in scored_clips) if scored_clips else 0,
                "max": max(c.get('final_score', 0) for c in scored_clips) if scored_clips else 0,
                "avg": sum(c.get('final_score', 0) for c in scored_clips) / len(scored_clips) if scored_clips else 0
            }
        }
    }
    
    logger.info(f"Step 3 完成: 输入{len(timeline_data)}个切片，评分{len(scored_clips)}个，筛选出{len(high_score_clips)}个高分切片")
    logger.info(f"评分来源分布: {score_source_dist}")
    
    return result["clips"]