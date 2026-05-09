import sys
sys.path.insert(0, 'e:/ClipProject/autoclip-main1/autoclip-main')
from backend.pipeline.step6_video import run_step6_video
from pathlib import Path

project_id = 'a9e1527c-13a2-496d-a06a-5a80b3c5648e'
project_dir = Path(f'e:/ClipProject/autoclip-main1/autoclip-main/data/projects/{project_id}')
metadata_dir = project_dir / 'metadata'
titles_path = metadata_dir / 'step4_titles.json'
collections_path = metadata_dir / 'step5_collections.json'
input_video = Path(r'E:\直播切片项目\output\20260420_新录制\clip_001_product_0s-708s.mp4')
clips_dir = project_dir / 'clips'
collections_dir = project_dir / 'collections'

print(f'Running step6 video generation...')
print(f'Input video: {input_video}')
print(f'Video exists: {input_video.exists()}')

video_result = run_step6_video(titles_path, collections_path, input_video, 
                               clips_dir=str(clips_dir), collections_dir=str(collections_dir), 
                               metadata_dir=str(metadata_dir))
print(f'Step6 result: {video_result}')

print('Step6 completed!')