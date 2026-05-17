"""
Step 4: 标题生成 - 为每个片段生成吸引人的标题
"""
import logging
from typing import List, Dict, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)


async def run_step4_title(
    project_id: str,
    metadata_dir: Path,
    clips: List[Dict[str, Any]],
    llm_client=None
) -> List[Dict[str, Any]]:
    """
    为每个片段生成标题

    Args:
        project_id: 项目ID
        metadata_dir: 元数据目录
        clips: 片段列表
        llm_client: LLM客户端

    Returns:
        更新后的片段列表
    """
    logger.info(f"Step 4: 为 {len(clips)} 个片段生成标题")

    # 为每个片段生成标题
    for clip in clips:
        # 优先使用outline作为标题
        title = ""
        outline = clip.get('outline', '')
        
        if isinstance(outline, dict):
            title = outline.get('title', '') or outline.get('content', '')
        elif isinstance(outline, str) and outline:
            title = outline
        
        # 如果没有outline，使用content
        if not title:
            content = clip.get('content', '')
            if content:
                # 使用内容的前50个字符作为标题
                title = content[:50] + "..." if len(content) > 50 else content
            else:
                # 如果都没有，生成一个简单标题
                clip_id = clip.get('id', 0)
                title = f"精彩片段{int(clip_id)+1}"
        
        clip["title"] = title

        # 确保content字段始终存在
        if "content" not in clip:
            clip["content"] = title

    # 保存结果
    output_file = metadata_dir / "step4_titles.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(clips, f, ensure_ascii=False, indent=2)

    logger.info(f"Step 4 完成: 标题已保存到 {output_file}")
    return clips
