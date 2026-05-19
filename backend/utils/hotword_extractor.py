"""
热词提取工具 - 借鉴 FunClip 的热词定制化思想

主要功能：
1. 从 SRT 数据中自动提取热词
2. 识别标志性开头词
3. 为后续步骤提供热词支持
"""
import re
import logging
from typing import List, Dict, Any, Optional
from collections import Counter
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# 常见标志性开头模式 - 从 FunClip 借鉴的思路
SIGNATURE_PATTERNS = [
    # 地域文化类标志性开头
    '京油子', '卫嘴子', '保定府的狗腿子',
    '北京人', '上海人', '广东人', '东北人',
    '北方人', '南方人', '河南人', '山东人',
    # 通用标志性开头
    '俗话说', '话说', '你知道', '你看', '我跟你说',
    '你知道吗', '你想啊', '你看啊', '我告诉你',
    '有句话说', '有这么句话', '你听说过吗',
    '我们都知道', '大家都知道', '众所周知',
    '今天讲', '今天说', '今天聊',
    '今天给大家讲', '今天给大家说', '今天给大家聊',
    '我们来聊', '我们来说', '我们来讲',
    '首先', '第一', '先来说', '先来看看',
]

# 停用词（不应该被提取为热词）
STOPWORDS = {
    '的', '是', '在', '了', '和', '与', '或',
    '以及', '等', '之', '于', '这', '那',
    '有', '我', '你', '他', '我们', '你们', '他们',
    '这个', '那个', '就是', '还是', '也是',
    '所以', '因为', '但是', '而且', '然后',
    '啊', '吧', '呢', '吗', '呀', '哦',
    '其实', '其实', '当然', '肯定', '确实',
    '什么', '怎么', '为什么', '怎么样',
    '不是', '不要', '不会', '不能',
    '还是', '只是', '只是', '还是',
}

class HotwordExtractor:
    """热词提取器"""

    def __init__(self, min_freq: int = 2, min_word_len: int = 2):
        self.min_freq = min_freq
        self.min_word_len = min_word_len

    def extract_from_srt(
        self,
        srt_data: List[Dict],
        top_k: int = 20
    ) -> List[Dict]:
        """
        从 SRT 数据中提取热词

        Args:
            srt_data: SRT 解析结果，每条包含 text, start_time, end_time
            top_k: 返回前 K 个热词

        Returns:
            [
                {
                    'word': '京油子',
                    'frequency': 5,
                    'is_signature': True,
                    'positions': [...]
                },
                ...
            ]
        """
        logger.info(f"从 SRT 数据中提取热词，共 {len(srt_data)} 条字幕")

        # 1. 收集所有文本
        all_text = " ".join([
            item.get('text', '')
            for item in srt_data
        ])

        # 2. 提取候选词
        candidate_words = self._extract_candidate_words(all_text)

        # 3. 统计词频
        word_counter = Counter(candidate_words)

        # 4. 过滤和排序
        hotwords = []
        for word, freq in word_counter.most_common(top_k * 2):
            if freq >= self.min_freq:
                hotword_info = {
                    'word': word,
                    'frequency': freq,
                    'is_signature': word in SIGNATURE_PATTERNS,
                    'positions': self._find_word_positions(word, srt_data)
                }
                hotwords.append(hotword_info)

        # 5. 排序：标志性开头优先，然后按词频
        hotwords.sort(
            key=lambda x: (not x['is_signature'], -x['frequency'])
        )

        hotwords = hotwords[:top_k]
        logger.info(f"提取到 {len(hotwords)} 个热词: {[w['word'] for w in hotwords]}")
        return hotwords

    def _extract_candidate_words(self, text: str) -> List[str]:
        """
        从文本中提取候选词（简单的中文分词）

        TODO: 可以集成 Jieba 等分词库提升准确率
        """
        words = []

        # 1. 先检查是否有已知的标志性词（完整匹配优先）
        for pattern in SIGNATURE_PATTERNS:
            if pattern in text:
                words.append(pattern)

        # 2. 按标点和空格分割
        separators = r'[，。！？；：、\s\n]'
        segments = re.split(separators, text)

        # 3. 提取 N-gram 和完整片段
        for segment in segments:
            segment = segment.strip()
            if len(segment) >= 2 and segment not in STOPWORDS:
                # 添加完整片段
                words.append(segment)

                # 添加 2-gram
                if len(segment) >= 4:
                    for i in range(len(segment) - 1):
                        bigram = segment[i:i+2]
                        if bigram not in STOPWORDS:
                            words.append(bigram)

        return words

    def _find_word_positions(
        self,
        word: str,
        srt_data: List[Dict]
    ) -> List[Dict]:
        """查找词在 SRT 中的位置"""
        positions = []

        for item in srt_data:
            text = item.get('text', '')
            if word in text:
                positions.append({
                    'start_time': item.get('start_time'),
                    'end_time': item.get('end_time'),
                    'text': text
                })

        return positions

    def get_signature_openings(
        self,
        hotwords: List[Dict]
    ) -> List[str]:
        """获取标志性开头词列表"""
        return [
            w['word']
            for w in hotwords
            if w['is_signature']
        ]

    def save_hotwords(self, hotwords: List[Dict], output_path: Path):
        """保存热词到文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(hotwords, f, ensure_ascii=False, indent=2)
        logger.info(f"热词已保存到: {output_path}")

    @staticmethod
    def load_hotwords(input_path: Path) -> List[str]:
        """从文件加载热词（简化版本）"""
        if not input_path.exists():
            return []
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                hotword_data = json.load(f)
                return [w['word'] for w in hotword_data]
        except Exception as e:
            logger.warning(f"加载热词失败: {e}")
            return []
