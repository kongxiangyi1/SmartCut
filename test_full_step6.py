import sys
from pathlib import Path

project_root = Path('.')
sys.path.insert(0, str(project_root))

project_id = '954f08fd-d15b-410e-bc1f-b051f9a40ba3'

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# 模拟项目路径
data_root = project_root / 'data' / 'projects' / project_id
input_dir = data_root / 'raw'
output_dir = data_root / 'output'
clips_dir = output_dir / 'clips'
collections_dir = output_dir / 'collections'
metadata_dir = output_dir / 'metadata'

# 确保目录存在
clips_dir.mkdir(parents=True, exist_ok=True)
collections_dir.mkdir(parents=True, exist_ok=True)

print(f'📁 项目目录: {data_root}')
print(f'📹 输入视频: {input_dir / "input.mp4"}')
print(f'📁 切片目录: {clips_dir}')

# 导入并运行实际的 Step 6
from backend.pipeline.step6_video import run_step6_video

# 检查输入文件是否存在
titles_path = metadata_dir / "step4_titles.json"
collections_path = metadata_dir / "step5_collections.json"
input_video_path = input_dir / "input.mp4"

print(f'\n📋 输入文件检查:')
print(f'  - step4_titles.json: {"存在" if titles_path.exists() else "不存在"}')
print(f'  - step5_collections.json: {"存在" if collections_path.exists() else "不存在"}')
print(f'  - input.mp4: {"存在" if input_video_path.exists() else "不存在"}')

# 读取 step4 的输出看看数据格式
if titles_path.exists():
    import json
    with open(titles_path, 'r', encoding='utf-8') as f:
        clips_data = json.load(f)
    print(f'\n📊 step4_titles.json 内容:')
    print(f'  片段数量: {len(clips_data)}')
    for clip in clips_data[:3]:
        print(f'  - ID: {clip["id"]}, 时间: {clip["start_time"]} -> {clip["end_time"]}')

# 运行 Step 6
print('\n🚀 开始运行 Step 6...')
result = run_step6_video(
    clips_with_titles_path=titles_path,
    collections_path=collections_path,
    input_video=input_video_path,
    output_dir=output_dir,
    clips_dir=str(clips_dir),
    collections_dir=str(collections_dir),
    metadata_dir=str(metadata_dir)
)

print(f'\n✅ Step 6 完成!')
print(f'  切片生成数量: {result["clips_generated"]}')
print(f'  合集生成数量: {result["collections_generated"]}')
print(f'  切片路径: {result["clip_paths"]}')

# 检查是否真的生成了文件
print(f'\n🔍 检查生成的文件:')
generated_clips = list(clips_dir.glob('*.mp4'))
print(f'  clips 目录中的 mp4 文件: {len(generated_clips)}')
for clip in generated_clips:
    size_mb = clip.stat().st_size / (1024 * 1024)
    print(f'    - {clip.name} ({size_mb:.2f} MB)')
