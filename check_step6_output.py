import json
from pathlib import Path

project_id = 'b0d4c113-3a61-4df7-a7f0-cc03759c3dc6'

# 检查 step6_video_output.json
step6_path = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\output\step6_video_output.json')
if step6_path.exists():
    with open(step6_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print('step6_video_output.json 的内容:')
    print(f"  键: {list(data.keys())}")
    
    if 'clips_with_titles' in data:
        clips = data['clips_with_titles']
        print(f"\n  clips_with_titles 数量: {len(clips)}")
        for i, clip in enumerate(clips[:2], 1):
            print(f"\n  切片 {i}:")
            print(f"    所有键: {list(clip.keys())}")
            print(f"    id: {clip.get('id')}")
            print(f"    duration: {clip.get('duration', 'N/A')}")
            print(f"    generated_title: {clip.get('generated_title', 'N/A')[:30]}...")
