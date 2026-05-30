from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import logging

try:
    import pycorrector
except ImportError:
    pycorrector = None

logger = logging.getLogger(__name__)

# 填充词列表（预处理时剔除——只剔除无意义的口吃/犹豫/套话）
FILLER_WORDS = {
    '嗯', '呃', '哦', '嗯嗯', '呃呃',
    '哈哈', '嘿嘿',
    '那个', '那个啥', '这个', '这个这个', '那个那个',
    '然后然后', '就是就是', '那个那个',
    '我们可以看到', '大家可以看到',
    '总的来说', '总的来说呢',
}


def _clean_filler_words(text: str) -> str:
    """从文本中剔除填充词"""
    for word in sorted(FILLER_WORDS, key=len, reverse=True):
        text = re.sub(re.escape(word), '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _safe_correct_line(text: str) -> str:
    """单行文本的安全纠正（不使用pycorrector，不改时间戳结构）"""
    text = _clean_filler_words(text)
    for wrong, right in TextCorrector.COMMON_RULES.items():
        text = text.replace(wrong, right)
    for wrong, right in TextCorrector.HOMOPHONE_RULES.items():
        text = text.replace(wrong, right)
    text = re.sub(r'([\u4e00-\u9fff])\1{1,}', r'\1', text)
    return text


def safe_correct_srt_file(srt_path: Path) -> bool:
    """
    对SRT文件做安全纠正（只改文本，不改时间戳和结构）。
    自动创建 .bak 备份。

    Args:
        srt_path: SRT文件路径

    Returns:
        是否做了修改
    """
    try:
        if not srt_path or not srt_path.exists():
            return False

        original_text = srt_path.read_text(encoding='utf-8')

        corrected_blocks = []
        blocks = original_text.strip().split('\n\n')

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                corrected_blocks.append(block)
                continue

            text_lines = lines[2:]
            corrected_text_lines = []
            for text_line in text_lines:
                if text_line.strip():
                    corrected_text_lines.append(_safe_correct_line(text_line))
                else:
                    corrected_text_lines.append(text_line)

            corrected_block = '\n'.join(lines[:2] + corrected_text_lines)
            corrected_blocks.append(corrected_block)

        corrected_text = '\n\n'.join(corrected_blocks) + '\n'

        if corrected_text == original_text:
            return False

        backup_path = srt_path.with_suffix('.srt.bak')
        if not backup_path.exists():
            backup_path.write_text(original_text, encoding='utf-8')

        srt_path.write_text(corrected_text, encoding='utf-8')
        logger.info(f"SRT纠正完成: {srt_path} (已备份到 {backup_path})")
        return True

    except Exception as e:
        logger.warning(f"SRT纠正写回失败（不影响主流程）: {e}")
        return False


class TextCorrector:
    """文本纠错与语义校验工具。"""

    COMMON_RULES = {
        '这个这个': '这个',
        '那个那个': '那个',
        '然后然后': '然后',
        '就是就是': '就是',
        '总的来说呢': '总的来说',
        '因为呢': '因为',
        '所以呢': '所以',
        '他说说': '他说',
        '其实其实': '其实',
        '反正反正': '反正',
        '能看见': '能看到',
        '我嘛': '我',
        '安利一下': '推荐一下',
    }

    HOMOPHONE_RULES = {
        '需呀': '需要',
        '赞亚': '咱呀',
        '发烧友': '发烧友',
        '重量级': '重量级',
    }

    def __init__(self, domain_dictionary: Optional[Dict[str, str]] = None):
        self.domain_dictionary = domain_dictionary or {}
        self.corrections: List[Dict[str, str]] = []

    def correct_text(self, text: str) -> Tuple[str, List[Dict[str, str]], float]:
        """对输入文本做纠错，返回纠错文本、元数据和置信度。"""
        self.corrections = []
        original = text

        text = self._apply_rule_corrections(text)
        text = self._apply_domain_corrections(text)

        corrected_by_pycorrector, py_details = self._apply_pycorrector_corrections(text)
        if corrected_by_pycorrector is not None:
            text = corrected_by_pycorrector

        validated_text = self._validate_semantic_corrections(text, original)
        text = validated_text

        confidence = self._estimate_confidence(original, text, py_details)
        return text, self.corrections, confidence

    def _apply_rule_corrections(self, text: str) -> str:
        corrected_text = text
        for wrong, right in self.COMMON_RULES.items():
            if wrong in corrected_text:
                corrected_text = corrected_text.replace(wrong, right)
                self.corrections.append({
                    'type': 'rule',
                    'source': wrong,
                    'target': right,
                    'reason': 'common phrase normalization'
                })

        # 合并重复的辅助词和停顿词
        corrected_text = re.sub(r'(\b[\u4e00-\u9fff]+)\1{1,}', r'\1', corrected_text)
        return corrected_text

    def _apply_domain_corrections(self, text: str) -> str:
        corrected_text = text
        for wrong, right in self.domain_dictionary.items():
            if wrong in corrected_text:
                corrected_text = corrected_text.replace(wrong, right)
                self.corrections.append({
                    'type': 'domain',
                    'source': wrong,
                    'target': right,
                    'reason': 'domain dictionary correction'
                })
        return corrected_text

    def _apply_pycorrector_corrections(self, text: str) -> Tuple[Optional[str], List[Dict[str, str]]]:
        if not pycorrector:
            return None, []

        try:
            corrected_text, detail = pycorrector.correct(text)
        except Exception:
            return None, []

        changes = []
        if corrected_text and corrected_text != text:
            for item in detail:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    wrong = item[0]
                    right = item[1]
                    changes.append({
                        'type': 'pycorrector',
                        'source': wrong,
                        'target': right,
                        'reason': 'pycorrector suggestion'
                    })
            self.corrections.extend(changes)
            return corrected_text, changes

        return None, []

    def _validate_semantic_corrections(self, text: str, original: str) -> str:
        if not original or text == original:
            return text

        similarity = self._text_similarity(original, text)
        if similarity < 0.55:
            self.corrections.append({
                'type': 'validation',
                'source': original,
                'target': original,
                'reason': 'semantic validation failed, reverted to original'
            })
            return original

        return text

    def _estimate_confidence(self, original: str, corrected: str,
                             py_details: List[Dict[str, str]]) -> float:
        if corrected == original:
            return 1.0
        if py_details:
            return 0.9
        if self.corrections:
            return 0.75
        return 0.8

    @staticmethod
    def _text_similarity(text1: str, text2: str) -> float:
        return SequenceMatcher(None, text1, text2).ratio()


class SemanticPreprocessor:
    """基于说话人/停顿的语义分段预处理器。"""

    SPEAKER_PATTERN = re.compile(r'^([\u4e00-\u9fffA-Za-z0-9_]+[:：])')

    @staticmethod
    def parse_srt_text(srt_text: str) -> List[Dict[str, object]]:
        entries = []
        blocks = re.split(r'\n\s*\n', srt_text.strip())
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            time_line = lines[1]
            time_match = re.match(
                r'(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})',
                time_line,
            )
            if not time_match:
                continue
            start = SemanticPreprocessor._to_seconds(time_match.group(1))
            end = SemanticPreprocessor._to_seconds(time_match.group(2))
            text = ' '.join(lines[2:]).strip()
            entries.append({
                'start': start,
                'end': end,
                'start_str': time_match.group(1).replace('.', ','),
                'end_str': time_match.group(2).replace('.', ','),
                'text': text,
            })
        entries.sort(key=lambda e: e['start'])
        return entries

    @staticmethod
    def generate_semantic_chunks(srt_entries: List[Dict[str, object]],
                                 pause_threshold_sec: float = 0.8) -> List[Dict[str, object]]:
        if not srt_entries:
            return []

        merged = SemanticPreprocessor._merge_speaker_segments(srt_entries)
        chunks = []
        current_chunk = [merged[0]]

        for prev, current in zip(merged, merged[1:]):
            pause = current['start'] - prev['end']
            if pause >= pause_threshold_sec or SemanticPreprocessor._is_new_speaker(prev['text'], current['text']):
                chunks.append(SemanticPreprocessor._build_chunk(current_chunk))
                current_chunk = [current]
            else:
                current_chunk.append(current)

        if current_chunk:
            chunks.append(SemanticPreprocessor._build_chunk(current_chunk))

        return chunks

    @staticmethod
    def _merge_speaker_segments(entries: List[Dict[str, object]]) -> List[Dict[str, object]]:
        if not entries:
            return []

        merged = [entries[0].copy()]
        for entry in entries[1:]:
            last = merged[-1]
            last_speaker = SemanticPreprocessor._extract_speaker(last['text'])
            current_speaker = SemanticPreprocessor._extract_speaker(entry['text'])
            if last_speaker and current_speaker and last_speaker == current_speaker:
                last['end'] = entry['end']
                last['end_str'] = entry['end_str']
                last['text'] = f"{last['text']} {entry['text']}"
            else:
                merged.append(entry.copy())
        return merged

    @staticmethod
    def _is_new_speaker(prev_text: str, current_text: str) -> bool:
        prev_speaker = SemanticPreprocessor._extract_speaker(prev_text)
        current_speaker = SemanticPreprocessor._extract_speaker(current_text)
        return bool(current_speaker and current_speaker != prev_speaker)

    @staticmethod
    def _extract_speaker(text: str) -> Optional[str]:
        match = SemanticPreprocessor.SPEAKER_PATTERN.match(text)
        return match.group(1) if match else None

    @staticmethod
    def _build_chunk(entries: List[Dict[str, object]]) -> Dict[str, object]:
        text = ' '.join(entry['text'] for entry in entries).strip()
        return {
            'start': entries[0]['start'],
            'end': entries[-1]['end'],
            'start_str': entries[0]['start_str'],
            'end_str': entries[-1]['end_str'],
            'text': re.sub(r'\s+', ' ', text).strip(),
        }

    @staticmethod
    def _to_seconds(time_str: str) -> float:
        normalized = time_str.replace(',', '.')
        parts = normalized.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds, millis = parts[2].split('.')
        return hours * 3600 + minutes * 60 + int(seconds) + int(millis) / 1000.0
