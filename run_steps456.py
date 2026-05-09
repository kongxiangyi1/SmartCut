import sys
sys.path.insert(0, 'e:/ClipProject/autoclip-main1/autoclip-main')
from backend.pipeline.step4_title import run_step4_title
from backend.pipeline.step5_clustering import run_step5_clustering
from backend.pipeline.step6_video import run_step6_video
from pathlib import Path

project_id = 'a9e1527c-13a2-496d-a06a-5a80b3c5648e'
project_dir = Path(f'e:/ClipProject/autoclip-main1/autoclip-main/data/projects/{project_id}')
metadata_dir = project_dir / 'metadata'
high_score_clips_path = metadata_dir / 'step3_high_score_clips.json'
titles_path = metadata_dir / 'step4_titles.json'
collections_path = metadata_dir / 'step5_collections.json'
input_video = project_dir / 'input.mp4'
clips_dir = project_dir / 'clips'
collections_dir = project_dir / 'collections'

print(f'Running step4-6 for project {project_id}')

print('Running step4 title generation...')
clips_with_titles = run_step4_title(high_score_clips_path, metadata_dir=metadata_dir)
print(f'Step4 generated titles for {len(clips_with_titles)} clips')

print('Running step5 clustering...')
collections = run_step5_clustering(titles_path, metadata_dir=metadata_dir)
print(f'Step5 generated {len(collections)} collections')

print('Running step6 video generation...')
video_result = run_step6_video(titles_path, collections_path, input_video, 
                               clips_dir=str(clips_dir), collections_dir=str(collections_dir), 
                               metadata_dir=str(metadata_dir))
print(f'Step6 result: {video_result}')

print('Pipeline completed!')