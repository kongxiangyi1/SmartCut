"""
Step 4: 标题生成 - 为每个片段生成吸引人的标题（优化版）

新增功能：
- 热词加载
- 标志性开头识别
- 热词前置优化
"""
import logging
from typing import List, Dict, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# 导入热词相关模块
from ..utils.hotword_extractor import SIGNATURE_PATTERNS


def _load_hotwords(metadata_dir: Path) -> List[str]:
    """从文件加载热词"""
    hotwords_file = metadata_dir / "step1_hotwords.json"
    if hotwords_file.exists():
        try:
            with open(hotwords_file, 'r', encoding='utf-8') as f:
                hotword_data = json.load(f)
                return [w['word'] for w in hotword_data]
        except Exception as e:
            logger.warning(f"加载热词失败: {e}")
    return []


def _find_signature_in_content(content: str) -> str:
    """在内容中查找标志性开头"""
    for pattern in SIGNATURE_PATTERNS:
        if pattern in content:
            idx = content.find(pattern)
            if idx >= 0:
                # 找到从标志性开头到第一个句号的内容
                end_idx = content.find('。', idx)
                if end_idx > idx:
                    return content[idx:end_idx+1]
                else:
                    # 如果没有句号，返回标志性开头本身
                    return pattern
    return ""


def _optimize_title_with_signature(title: str, clip: Dict, hotwords: List[str]) -> str:
    """
    优化标题 - 保留标志性开头

    借鉴 FunClip 的热词定制化思路
    """
    content = clip.get('content', '')

    # 1. 查找标志性开头
    signature = _find_signature_in_content(content)
    if signature:
        # 如果标题中没有包含标志性开头，添加到前面
        if signature not in title:
            return f"{signature}：{title}"

    # 2. 如果没有标志性开头，检查是否有热词
    if hotwords:
        for hotword in hotwords:
            if hotword in content and hotword not in title:
                # 标题中没有热词，但内容中有，添加到前面
                return f"{hotword}：{title}"

    return title


async def run_step4_title(
    project_id: str,
    metadata_dir: Path,
    clips: List[Dict[str, Any]],
    llm_client=None
) -> List[Dict[str, Any]]:
    """
    为每个片段生成标题（优化版）

    新增功能：
    - 加载热词
    - 标志性开头识别
    - 热词前置

    Args:
        project_id: 项目ID
        metadata_dir: 元数据目录
        clips: 片段列表
        llm_client: LLM客户端

    Returns:
        更新后的片段列表
    """
    logger.info(f"Step 4: 为 {len(clips)} 个片段生成标题（优化版）")

    # 【新增】加载热词
    hotwords = _load_hotwords(metadata_dir)
    if hotwords:
        logger.info(f"加载到 {len(hotwords)} 个热词: {hotwords[:10]}")

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

        # 【新增】优化标题 - 保留标志性开头
        optimized_title = _optimize_title_with_signature(title, clip, hotwords)
        clip["title"] = optimized_title

        # 确保content字段始终存在
        if "content" not in clip:
            clip["content"] = optimized_title

    # 保存结果
    output_file = metadata_dir / "step4_titles.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(clips, f, ensure_ascii=False, indent=2)

    logger.info(f"Step 4 完成: 标题已保存到 {output_file}")
    return clips
