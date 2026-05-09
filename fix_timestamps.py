"""
修复项目数据中的时间戳问题

将时间戳限制在视频实际时长范围内。
"""
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_timestamps_to_video_duration(project_id: str, video_duration: float = 708.03):
    project_dir = Path(f"d:/Download/autoclip-main1/autoclip-main/data/projects/{project_id}")
    metadata_dir = project_dir / "metadata"

    files_to_fix = [
        metadata_dir / "step4_titles.json",
        metadata_dir / "step5_collections.json",
        metadata_dir / "step2_timeline.json",
        metadata_dir / "step3_all_scored.json",
        metadata_dir / "step3_high_score_clips.json",
        metadata_dir / "clips_metadata.json",
    ]

    for file_path in files_to_fix:
        if not file_path.exists():
            logger.warning(f"文件不存在，跳过: {file_path}")
            continue

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            logger.warning(f"{file_path.name} 不是列表，跳过")
            continue

        fixed_count = 0
        for item in data:
            start_time = item.get('start_time', '00:00:00,000')
            end_time = item.get('end_time', '00:00:00,000')

            start_sec = parse_time_to_seconds(start_time)
            end_sec = parse_time_to_seconds(end_time)

            if start_sec > video_duration:
                old_start = start_time
                start_time = format_seconds_to_time(video_duration - 1)
                item['start_time'] = start_time
                fixed_count += 1
                logger.info(f"Fixed start: {old_start} -> {start_time}")

            if end_sec > video_duration:
                old_end = end_time
                end_time = format_seconds_to_time(video_duration)
                item['end_time'] = end_time
                fixed_count += 1
                logger.info(f"Fixed end: {old_end} -> {end_time}")

            new_start_sec = parse_time_to_seconds(item['start_time'])
            new_end_sec = parse_time_to_seconds(item['end_time'])
            if new_start_sec >= new_end_sec:
                item['end_time'] = format_seconds_to_time(new_start_sec + 1)
                logger.info(f"Adjusted end to be after start: {item['end_time']}")

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"修复 {file_path.name}: 共修复 {fixed_count} 个时间戳")

    logger.info("时间戳修复完成")
    return True

def parse_time_to_seconds(time_str: str) -> float:
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    return 0

def format_seconds_to_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02}:{minutes:02}:{secs:06.3f}".replace('.', ',')

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
    else:
        project_id = "4cdb7de0-07aa-4c35-97fc-07c382c51af2"
    fix_timestamps_to_video_duration(project_id)
