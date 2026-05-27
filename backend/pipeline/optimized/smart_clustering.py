"""
Step 2 优化版：智能聚类器
本地关键词聚类为主，LLM微调为辅
"""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import Counter

from ..utils.llm_client import LLMClient
from ..core.shared_config import MAX_CLIPS_PER_COLLECTION

logger = logging.getLogger(__name__)

# 主题关键词映射
THEME_KEYWORDS = {
    '投资理财': ['投资', '理财', '股票', '基金', '炒股', '赚钱', '收益', '涨跌', '解套', '散户', 'A股', '北交所'],
    '职场成长': ['职场', '工作', '技能', '学习', '日语', '董秘', '逆袭', '教育', '大学生', '财商'],
    '社会观察': ['社会', '现象', '网络', '乱象', '垃圾', '分类', '平台', '机制', '主播', '行业'],
    '文化差异': ['文化', '差异', '欧美', '日本', '韩国', '饮食', '语言', '狐臭', '蒸锅', '邮轮'],
    '直播互动': ['直播', '互动', '弹幕', '粉丝', '舰长', '打赏', '连麦', 'PK', '抽奖'],
    '情感关系': ['恋爱', '情感', '社交', '搭讪', '关系', '心理', '心动', '冷淡'],
    '健康生活': ['健康', '运动', '跑步', '饮食', '牛奶', '生活方式', '锻炼'],
    '创作平台': ['创作', '平台', 'B站', '小红书', '摄影', '内容', '运营', '自媒体']
}

# 主题标题映射
THEME_TITLES = {
    '投资理财': '投资理财启示',
    '职场成长': '职场成长记',
    '社会观察': '社会观察笔记',
    '文化差异': '文化差异趣谈',
    '直播互动': '直播互动现场',
    '情感关系': '情感与关系',
    '健康生活': '健康生活方式',
    '创作平台': '创作与平台生态'
}

# 主题简介映射
THEME_SUMMARIES = {
    '投资理财': '通过生活化案例分享投资理念，兼具实用与共鸣。',
    '职场成长': '探讨职业发展、技能提升与职场心态变化。',
    '社会观察': '理性点评社会现象与网络乱象，观点鲜明。',
    '文化差异': '从饮食到语言，展现跨文化交流的趣味视角。',
    '直播互动': '还原真实直播间互动场景，展现主播临场反应。',
    '情感关系': '解析恋爱心理、社交困惑与情感共鸣话题。',
    '健康生活': '分享运动、饮食、心理调适等健康管理经验。',
    '创作平台': '剖析内容创作困境与平台机制，适合创作者参考。'
}


class SmartClusterer:
    """
    智能聚类器 - 优化版
    
    优先使用本地关键词聚类，显著减少LLM调用
    仅在需要时调用LLM进行微调
    """
    
    def __init__(self):
        self.llm_client = LLMClient()
    
    def cluster(self, clips: List[Dict], use_llm_refine: bool = False) -> List[Dict]:
        """
        执行智能聚类
        
        Args:
            clips: 切片列表（来自unified_analyzer）
            use_llm_refine: 是否使用LLM微调
            
        Returns:
            合集列表
        """
        logger.info(f"开始智能聚类（{len(clips)} 个切片）...")
        
        # 1. 本地关键词预聚类
        pre_clusters = self._keyword_based_clustering(clips)
        logger.info(f"预聚类完成: {len(pre_clusters)} 个主题")
        
        # 2. 创建合集
        collections = self._create_collections(pre_clusters, clips)
        
        # 3. 可选：LLM微调
        if use_llm_refine and collections:
            logger.info("使用LLM进行聚类微调...")
            collections = self._llm_refine_collections(collections, clips)
        
        logger.info(f"聚类完成: {len(collections)} 个合集")
        return collections
    
    def _keyword_based_clustering(self, clips: List[Dict]) -> Dict[str, List[str]]:
        """
        基于关键词的预聚类（完全本地处理，无需LLM）
        
        Args:
            clips: 切片列表
            
        Returns:
            {主题: [clip_id列表]}
        """
        clusters = {theme: [] for theme in THEME_KEYWORDS.keys()}
        unclustered = []
        
        for clip in clips:
            clip_id = clip.get('id')
            
            # 合并标题、理由、内容进行关键词匹配
            text = ' '.join([
                clip.get('generated_title', ''),
                clip.get('outline', ''),
                clip.get('recommend_reason', ''),
                ' '.join(clip.get('content', []))
            ]).lower()
            
            # 计算每个主题的匹配分数
            theme_scores = {}
            for theme, keywords in THEME_KEYWORDS.items():
                score = sum(1 for kw in keywords if kw in text)
                if score > 0:
                    theme_scores[theme] = score
            
            # 选择最佳匹配主题
            if theme_scores:
                best_theme = max(theme_scores.keys(), key=lambda k: theme_scores[k])
                clusters[best_theme].append(clip_id)
            else:
                unclustered.append(clip_id)
        
        # 过滤空主题
        clusters = {k: v for k, v in clusters.items() if len(v) >= 2}
        
        # 未聚类的片段按时间顺序组成合集
        if unclustered:
            clusters['其他内容'] = unclustered
        
        return clusters
    
    def _create_collections(self, clusters: Dict[str, List[str]], 
                           clips: List[Dict]) -> List[Dict]:
        """
        从聚类创建合集
        
        Args:
            clusters: 预聚类结果
            clips: 切片列表
            
        Returns:
            合集列表
        """
        clip_map = {c['id']: c for c in clips}
        collections = []
        
        for theme, clip_ids in clusters.items():
            # 限制每个合集的切片数量
            if len(clip_ids) > MAX_CLIPS_PER_COLLECTION:
                clip_ids = clip_ids[:MAX_CLIPS_PER_COLLECTION]
            
            # 获取切片详情并按评分排序
            clip_details = []
            for clip_id in clip_ids:
                clip = clip_map.get(clip_id)
                if clip:
                    clip_details.append({
                        'id': clip_id,
                        'title': clip.get('generated_title', clip.get('outline', '')),
                        'score': clip.get('final_score', 0)
                    })
            
            # 按评分排序
            clip_details.sort(key=lambda x: x['score'], reverse=True)
            
            # 创建合集
            if theme in THEME_TITLES:
                collection_title = THEME_TITLES[theme]
                collection_summary = THEME_SUMMARIES[theme]
            else:
                collection_title = f'{theme}相关合集'
                collection_summary = '精选内容合集'
            
            collections.append({
                'id': str(len(collections) + 1),
                'collection_title': collection_title,
                'collection_summary': collection_summary,
                'clip_ids': clip_ids,
                'theme': theme
            })
        
        return collections
    
    def _llm_refine_collections(self, collections: List[Dict],
                                clips: List[Dict]) -> List[Dict]:
        """
        使用LLM微调合集（可选，降低API调用频率）
        
        Args:
            collections: 当前合集列表
            clips: 切片列表
            
        Returns:
            微调后的合集列表
        """
        if len(collections) <= 3:
            return collections
        
        try:
            # 构建LLM输入
            clip_info = [
                {
                    'id': c['id'],
                    'title': c.get('generated_title', c.get('outline', '')),
                    'score': c.get('final_score', 0)
                }
                for c in clips
            ]
            
            prompt = """你是一位视频内容策划专家，请优化以下合集：
- 每个合集最多5个切片
- 确保合集内切片主题高度一致
- 考虑切片评分和质量

请返回优化后的合集配置。"""
            
            # LLM微调调用（仅1次）
            response = self.llm_client.call_with_retry(prompt, {'clips': clip_info})
            
            if response:
                refined = self.llm_client.parse_json_response(response)
                if isinstance(refined, list):
                    return refined
            
        except Exception as e:
            logger.warning(f"LLM微调失败: {e}")
        
        return collections


def run_smart_clustering(clips: List[Dict], use_llm_refine: bool = False) -> List[Dict]:
    """
    运行智能聚类
    
    Args:
        clips: 切片列表
        use_llm_refine: 是否使用LLM微调
        
    Returns:
        合集列表
    """
    clusterer = SmartClusterer()
    return clusterer.cluster(clips, use_llm_refine)
