import json
from pathlib import Path

timeline = Path('e:/ClipProject/autoclip-main1/autoclip-main/data/projects/a9e1527c-13a2-496d-a06a-5a80b3c5648e/metadata/step2_timeline.json')
data = json.loads(timeline.read_text(encoding='utf-8'))

print(f'时间线片段数量: {len(data)}')
if data:
    first = data[0]
    last = data[-1]
    print(f'第一个片段: {first["start_time"]} --> {first["end_time"]}')
    print(f'最后一个片段: {last["start_time"]} --> {last["end_time"]}')

    def to_seconds(time_str):
        parts = time_str.replace(',', '.').split(':')
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

    first_start = to_seconds(first['start_time'])
    last_end = to_seconds(last['end_time'])
    print(f'\n覆盖时间范围: {first_start:.1f}秒 到 {last_end:.1f}秒')
    print(f'覆盖总时长: {last_end - first_start:.1f}秒 = {(last_end - first_start) / 60:.1f}分钟')
