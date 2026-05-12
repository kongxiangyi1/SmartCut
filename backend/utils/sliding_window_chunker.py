"""
滑动窗口分块器
通过重叠分块策略，减少话题被切断的问题
"""
import logging
from typing import List, Dict, Any, Optional
from ..core.shared_config import CHUNK_SIZE

logger = logging.getLogger(__name__)


class SlidingWindowChunker:
    def __init__(
        self,
        chunk_size: int = 300,
        overlap_minutes: int = 1,
        min_chunk_size: int = 60
    ):
        self.chunk_size = chunk_size
        self.overlap_seconds = overlap_minutes * 60
        self.min_chunk_size = min_chunk_size

    def chunk_text(
        self,
        text: str,
        subtitles: List[Dict],
        time_offset: int = 0
    ) -> List[Dict]:
        if not subtitles:
            return []

        logger.info(f"滑动窗口分块: chunk_size={self.chunk_size}s, overlap={self.overlap_seconds}s")

        subtitles_with_seconds = []
        for sub in subtitles:
            entry = sub.copy()
            entry['start_seconds'] = self._time_to_seconds(sub['start_time'])
            entry['end_seconds'] = self._time_to_seconds(sub['end_time'])
            subtitles_with_seconds.append(entry)

        total_duration = subtitles_with_seconds[-1]['end_seconds']
        chunks = []
        chunk_index = 0
        current_start = 0

        while current_start < len(subtitles_with_seconds):
            chunk_start_time = subtitles_with_seconds[current_start]['start_seconds']
            chunk_end_time = min(chunk_start_time + self.chunk_size, total_duration)

            search_end = chunk_end_time
            if current_start > 0:
                search_end = min(chunk_end_time + self.overlap_seconds, total_duration)

            end_index = self._find_best_cut_index(
                subtitles_with_seconds,
                current_start,
                search_end,
                chunk_end_time
            )

            chunk_subtitles = subtitles_with_seconds[current_start:end_index]
            if not chunk_subtitles:
                break

            chunk_text = " ".join([entry['text'] for entry in chunk_subtitles])
            chunks.append({
                "chunk_index": chunk_index,
                "text": chunk_text,
                "start_time": chunk_subtitles[0]['start_time'],
                "end_time": chunk_subtitles[-1]['end_time'],
                "start_seconds": chunk_subtitles[0]['start_seconds'],
                "end_seconds": chunk_subtitles[-1]['end_seconds'],
                "srt_entries": self._clean_entries(chunk_subtitles),
                "is_first": chunk_index == 0,
                "is_last": end_index >= len(subtitles_with_seconds)
            })

            if end_index >= len(subtitles_with_seconds):
                break

            next_start = end_index - self._count_overlap_entries(
                subtitles_with_seconds,
                current_start,
                end_index
            )
            next_start = max(next_start, current_start + 1)
            current_start = next_start
            chunk_index += 1

        logger.info(f"滑动窗口分块完成: 共 {len(chunks)} 个块")
        return chunks

    def _find_best_cut_index(
        self,
        subtitles: List[Dict],
        start_index: int,
        search_end: float,
        target_end: float
    ) -> int:
        best_index = start_index + 1

        for i in range(start_index + 1, len(subtitles)):
            if subtitles[i]['start_seconds'] > search_end:
                break
            if subtitles[i]['start_seconds'] <= target_end:
                pause = subtitles[i]['start_seconds'] - subtitles[i-1]['end_seconds']
                if pause >= 1.0:
                    best_index = i
            elif subtitles[i]['start_seconds'] > target_end * 0.9:
                best_index = i
                break

        return max(best_index, start_index + 1)

    def _count_overlap_entries(
        self,
        subtitles: List[Dict],
        start_index: int,
        end_index: int
    ) -> int:
        if end_index >= len(subtitles):
            return 0
        overlap_start = subtitles[end_index - 1]['end_seconds']
        count = 0
        for i in range(end_index, len(subtitles)):
            if subtitles[i]['start_seconds'] - overlap_start < self.overlap_seconds:
                count += 1
            else:
                break
        return count

    def _clean_entries(self, entries: List[Dict]) -> List[Dict]:
        clean = []
        for entry in entries:
            e = entry.copy()
            e.pop('start_seconds', None)
            e.pop('end_seconds', None)
            clean.append(e)
        return clean

    @staticmethod
    def _time_to_seconds(time_str: str) -> float:
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
        elif len(parts) == 2:
            minutes, seconds = parts
            return float(minutes) * 60 + float(seconds)
        return 0.0
