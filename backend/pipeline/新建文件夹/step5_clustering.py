"""
Step 5: 聚类 - 将相似主题的片段分组
"""
import logging
from typing import List, Dict, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)


async def run_step5_clustering(
    project_id: str,
    metadata_dir: Path,
    clips: List[Dict[str, Any]],
    llm_client=None
) -> List[Dict[str, Any]]:
    """
    将片段按主题聚类

    Args:
        project_id: 项目ID
        metadata_dir: 元数据目录
        clips: 片段列表
        llm_client: LLM客户端

    Returns:
        聚类后的合集列表
    """
    logger.info(f"Step 5: 对 {len(clips)} 个片段进行聚类")

    # 简单的聚类逻辑：将连续片段分组
    clusters = []
    current_cluster = []

    for i, clip in enumerate(clips):
        current_cluster.append(clip)
        # 每3个片段创建一个聚类
        if len(current_cluster) >= 3 or i == len(clips) - 1:
            # 构建clip_ids列表
            clip_ids = []
            for c in current_cluster:
                if isinstance(c.get('id'), (int, str)):
                    clip_ids.append(str(c['id']))
                elif isinstance(c.get('index'), int):
                    clip_ids.append(str(c['index']))
            
            clusters.append({
                "id": str(len(clusters)),
                "collection_title": f"精彩合集 {len(clusters) + 1}",
                "description": f"精选视频片段",
                "clip_ids": clip_ids,
                "clips": current_cluster.copy()
            })
            current_cluster = []

    # 保存结果
    output_file = metadata_dir / "step5_clusters.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(clusters, f, ensure_ascii=False, indent=2)

    logger.info(f"Step 5 完成: 聚类结果已保存到 {output_file}")
    return clusters
