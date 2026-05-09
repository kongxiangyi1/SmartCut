"""
根据视频实际时长重新分配时间戳
"""
import json
from pathlib import Path

project_id = "2716cdeb-fb3e-461d-87a8-312dcf077b9f"
project_dir = Path(f"d:/Download/autoclip-main1/autoclip-main/data/projects/{project_id}")
metadata_dir = project_dir / "metadata"

VIDEO_DURATION = 708.0

# 读取LLM原始输出（有正确的outline顺序）
llm_raw = metadata_dir / "step2_llm_raw_output" / "chunk_0_attempt_0.txt"
with open(llm_raw, 'r', encoding='utf-8') as f:
    llm_data = json.load(f)

# 根据outline匹配来分配时间戳
# 首先获取所有clips的outline
clips_file = metadata_dir / "clips_metadata.json"
with open(clips_file, 'r', encoding='utf-8') as f:
    clips_data = json.load(f)

# 建立outline到LLM数据的映射
llm_by_outline = {item['outline']: item for item in llm_data}

# 收集所有有内容的clip
valid_clips = []
for clip in clips_data:
    outline = clip['outline']
    if outline in llm_by_outline:
        valid_clips.append({
            'outline': outline,
            'llm_item': llm_by_outline[outline],
            'clip': clip
        })

print(f"找到 {len(valid_clips)} 个有效clips")

# 计算每个clip应该分配的时间比例（基于内容长度）
total_content_length = sum(len(c['llm_item']['content']) for c in valid_clips)
print(f"总内容长度: {total_content_length}")

# 为每个clip分配时间段
num_clips = len(valid_clips)
if num_clips == 0:
    print("没有有效的clips")
    exit(1)

# 将视频时长按比例分配
MIN_CLIP_DURATION = 3.0  # 最少3秒

clip_times = []
current_time = 0.0
for i, vc in enumerate(valid_clips):
    if i == num_clips - 1:
        # 最后一个clip到视频结束
        end_time = VIDEO_DURATION
    else:
        # 按内容比例分配，但保证最少MIN_CLIP_DURATION
        content_ratio = len(vc['llm_item']['content']) / total_content_length
        allocated_duration = max(MIN_CLIP_DURATION, (VIDEO_DURATION - current_time) * content_ratio)
        # 但不能超过剩余时间
        remaining_time = VIDEO_DURATION - current_time - (num_clips - i - 1) * MIN_CLIP_DURATION
        allocated_duration = min(allocated_duration, remaining_time)
        end_time = current_time + allocated_duration

    clip_times.append((current_time, end_time))
    current_time = end_time

# 打印分配的时间
for i, vc in enumerate(valid_clips):
    start, end = clip_times[i]
    duration = end - start
    print(f"Clip {vc['clip']['id']}: {start:.1f}s - {end:.1f}s (duration: {duration:.1f}s)")

# 更新所有相关文件
def format_time(seconds):
    seconds = max(0, min(seconds, VIDEO_DURATION))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')

files_to_fix = [
    metadata_dir / "step4_titles.json",
    metadata_dir / "step2_timeline.json",
    metadata_dir / "step3_all_scored.json",
    metadata_dir / "step3_high_score_clips.json",
    metadata_dir / "clips_metadata.json",
]

for file_path in files_to_fix:
    if not file_path.exists():
        print(f"跳过不存在的文件: {file_path.name}")
        continue

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"跳过非列表文件: {file_path.name}")
        continue

    fixed_count = 0
    for item in data:
        outline = item.get('outline', '')
        for i, vc in enumerate(valid_clips):
            if vc['outline'] == outline:
                start, end = clip_times[i]
                item['start_time'] = format_time(start)
                item['end_time'] = format_time(end)
                fixed_count += 1
                break

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"修复 {file_path.name}: {fixed_count} 个时间戳")

print("所有文件修复完成！")
