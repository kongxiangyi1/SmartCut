"""
Step 3: 内容评分 - 对每个话题进行质量评分，筛选出高质量内容
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict

# 导入依赖
from ..core.llm_manager import LLMManager
from ..utils.text_processor import TextProcessor
from ..core.shared_config import PROMPT_FILES, METADATA_DIR, MIN_SCORE_THRESHOLD

logger = logging.getLogger(__name__)

class ClipScorer:
    """内容评分器"""
    
    def __init__(self, prompt_files: Dict = None):
        self.llm_manager = LLMManager()
        self.text_processor = TextProcessor()
        
        # 加载提示词
        prompt_files_to_use = prompt_files if prompt_files is not None else PROMPT_FILES
        with open(prompt_files_to_use['recommendation'], 'r', encoding='utf-8') as f:
            self.recommendation_prompt = f.read()
    
    def score_clips(self, timeline_data: List[Dict]) -> List[Dict]:
        """
        为切片评分 (新版：按块批量处理，并使用LLM进行综合评估)
        """
        if not timeline_data:
            logger.warning("时间线数据为空，无法评分")
            return []
            
        logger.info(f"开始为 {len(timeline_data)} 个切片进行批量评分...")
        
        # 1. 按 chunk_index 对所有 timeline 数据进行分组
        timeline_by_chunk = defaultdict(list)
        for item in timeline_data:
            chunk_index = item.get('chunk_index')
            if chunk_index is not None:
                timeline_by_chunk[chunk_index].append(item)
            else:
                logger.warning(f"  > 话题 '{item.get('outline', '未知')}' 缺少 chunk_index，将被跳过。")
        
        all_scored_clips = []
        # 2. 遍历每个块，批量处理其中的所有话题
        for chunk_index, chunk_items in timeline_by_chunk.items():
            logger.info(f"处理块 {chunk_index}，其中包含 {len(chunk_items)} 个话题...")
            try:
                # 3. 使用LLM进行批量评估
                scored_chunk_items = self._get_llm_evaluation(chunk_items)
                
                if scored_chunk_items:
                    all_scored_clips.extend(scored_chunk_items)
                else:
                    logger.warning(f"块 {chunk_index} 的LLM评估返回为空，跳过。")

            except Exception as e:
                logger.error(f"  > 处理块 {chunk_index} 进行评分时出错: {str(e)}")
                continue

        # 4. 按最终得分对所有结果进行排序
        if all_scored_clips:
            all_scored_clips.sort(key=lambda x: x.get('final_score', 0), reverse=True)
            # 保持Step 2分配的固定ID，不再重新分配
            logger.info("按评分排序完成，保持原有固定ID不变")
            
            # 最终按ID排序，确保时间顺序的一致性
            all_scored_clips.sort(key=lambda x: int(x.get('id', 0)))
            logger.info("按ID排序完成，保持时间顺序")
                
        logger.info("所有切片评分完成")
        return all_scored_clips
    
    def _get_llm_evaluation(self, clips: List[Dict]) -> List[Dict]:
        """
        使用LLM进行批量评估，为每个clip添加 final_score 和 recommend_reason
        """
        try:
            # 输入给LLM的数据不需要包含所有字段，只给必要的
            input_for_llm = [
                {
                    "outline": clip.get('outline'), 
                    "content": clip.get('content'),
                    "start_time": clip.get('start_time'),
                    "end_time": clip.get('end_time'),
                } for clip in clips
            ]
            
            response = self.llm_manager.call_with_retry(self.recommendation_prompt, input_for_llm)
            parsed_list = self.llm_manager.parse_json_response(response)
            
            if not isinstance(parsed_list, list) or len(parsed_list) != len(clips):
                logger.error(f"LLM返回的评分结果数量与输入不匹配。输入: {len(clips)}, 输出: {len(parsed_list)}")
                return []
                
            # 将评分结果合并回原始的clips数据
            for original_clip, llm_result in zip(clips, parsed_list):
                score = llm_result.get('final_score')
                reason = llm_result.get('recommend_reason')
                
                if score is None or reason is None:
                    logger.warning(f"LLM返回的某个结果缺少score或reason: {llm_result}")
                    original_clip['final_score'] = 0.0
                    original_clip['recommend_reason'] = "评估失败"
                else:
                    original_clip['final_score'] = round(float(score), 2)
                    original_clip['recommend_reason'] = reason
                    outline = original_clip.get('outline', {})
                    if isinstance(outline, dict):
                        title = outline.get('title', '未知标题')
                    else:
                        title = str(outline)
                    logger.info(f"  > 评分成功: {title[:20]}... [分数: {score}]")

            # 强制分数差异化：防止LLM返回全相同的分数
            clips = self._ensure_score_diversity(clips)

            return clips

        except Exception as e:
            logger.error(f"LLM批量评估失败: {e}")
            # 如果批量失败，为所有clips标记为失败
            for clip in clips:
                clip['final_score'] = 0.0
                clip['recommend_reason'] = "批量评估失败"
            return clips

    def _ensure_score_diversity(self, clips: List[Dict]) -> List[Dict]:
        """强制分数差异化：当所有分数相同时，根据内容质量微调"""
        scores = [c.get('final_score', 0) for c in clips]
        unique_scores = set(scores)

        if len(unique_scores) <= 1 and len(clips) > 1:
            logger.warning(f"检测到所有分数相同({scores[0] if scores else 'N/A'})，强制差异化...")
            base_score = scores[0] if scores else 0.5
            diversified = []
            for i, clip in enumerate(clips):
                content = clip.get('content', '') or ''
                outline = clip.get('outline', {})
                if isinstance(outline, dict):
                    title = outline.get('title', '') or ''
                else:
                    title = str(outline)
                text_len = len(content) + len(title)

                variance = 0.0
                if text_len > 200:
                    variance = 0.15
                elif text_len > 100:
                    variance = 0.08
                elif text_len > 50:
                    variance = 0.03

                offset = (i / max(len(clips) - 1, 1)) * 0.2 - 0.1
                new_score = min(1.0, max(0.1, base_score + variance + offset))
                clip['final_score'] = round(new_score, 2)
                clip['recommend_reason'] = clip.get('recommend_reason', '') + ' (校准评分)'
                diversified.append(clip)

            logger.info(f"分数差异化完成: {[c['final_score'] for c in diversified]}")
            return diversified

        return clips

    def save_scores(self, scored_clips: List[Dict], output_path: Path):
        """保存评分结果"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(scored_clips, f, ensure_ascii=False, indent=2)
        logger.info(f"评分结果已保存到: {output_path}")

def run_step3_scoring(timeline_path: Path, metadata_dir: Path = None, output_path: Optional[Path] = None, prompt_files: Dict = None) -> List[Dict]:
    """
    运行Step 3: 内容评分与筛选
    
    Args:
        timeline_path: 时间线文件路径
        output_path: 输出文件路径
        prompt_files: 自定义提示词文件
        
    Returns:
        高分切片列表
    """
    # 加载时间线数据
    with open(timeline_path, 'r', encoding='utf-8') as f:
        timeline_data = json.load(f)
    
    # 创建评分器
    scorer = ClipScorer(prompt_files)
    
    # 评分
    scored_clips = scorer.score_clips(timeline_data)
    
    # 筛选高分切片
    high_score_clips = [clip for clip in scored_clips if clip['final_score'] >= MIN_SCORE_THRESHOLD]
    
    # 保存结果
    if metadata_dir is None:
        metadata_dir = METADATA_DIR
    
    # 保存所有评分后的片段（用于调试和分析）
    all_scored_path = metadata_dir / "step3_all_scored.json"
    scorer.save_scores(scored_clips, all_scored_path)
    
    # 保存筛选后的高分片段（用于后续步骤）
    if output_path is None:
        output_path = metadata_dir / "step3_high_score_clips.json"
        
    scorer.save_scores(high_score_clips, output_path)
    
    return high_score_clips