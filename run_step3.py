import sys
sys.path.insert(0, 'e:/ClipProject/autoclip-main1/autoclip-main')
from backend.pipeline.step3_scoring import run_step3_scoring
from pathlib import Path

project_id = 'a9e1527c-13a2-496d-a06a-5a80b3c5648e'
metadata_dir = Path(f'e:/ClipProject/autoclip-main1/autoclip-main/data/projects/{project_id}/metadata')
timeline_path = metadata_dir / 'step2_timeline.json'

print(f'Running step3 scoring for project {project_id}')
print(f'Timeline path: {timeline_path}')
print(f'Metadata dir: {metadata_dir}')

high_score_clips = run_step3_scoring(timeline_path, metadata_dir=metadata_dir)
print(f'High score clips: {len(high_score_clips)}')