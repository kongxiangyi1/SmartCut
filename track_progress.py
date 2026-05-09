import redis
import time
from pathlib import Path

def track_project(project_id):
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    project_path = Path(f'e:/ClipProject/autoclip-main1/autoclip-main/data/projects/{project_id}')

    print(f'开始跟踪项目: {project_id}')
    print('=' * 60)

    last_data = None
    same_count = 0

    while True:
        progress = r.hgetall(f'progress:project:{project_id}')

        if not progress:
            print('\n项目进度信息已消失（可能已完成或清除）')
            break

        stage = progress.get('stage', 'UNKNOWN')
        percent = int(progress.get('percent', 0))
        message = progress.get('message', '')

        current_data = (stage, percent, message)

        if current_data != last_data:
            timestamp = time.strftime("%H:%M:%S")
            print(f'[{timestamp}] 阶段: {stage} | 进度: {percent}% | {message}')

            if project_path.exists():
                metadata_dir = project_path / 'metadata'
                if metadata_dir.exists():
                    files = {f.name: f.stat().st_size / 1024 / 1024 for f in metadata_dir.iterdir()}
                    print(f'           文件: {list(files.keys())}')

            last_data = current_data
            same_count = 0
        else:
            same_count += 1
            if same_count >= 15:
                print(f'[{time.strftime("%H:%M:%S")}] 等待中... (相同状态已保持{same_count*2}秒)')

        if percent >= 100 or '完成' in message or 'error' in stage.lower():
            print('\n项目处理已完成!')
            break

        time.sleep(2)

    print('\n' + '=' * 60)
    print('最终项目状态:')
    if project_path.exists():
        metadata_dir = project_path / 'metadata'
        if metadata_dir.exists():
            print('\n所有生成的文件:')
            for f in sorted(metadata_dir.iterdir()):
                size_mb = f.stat().st_size / 1024 / 1024
                print(f'  {f.name}: {size_mb:.2f} MB')

        clips_dir = project_path / 'clips'
        if clips_dir.exists():
            clips = list(clips_dir.glob('*.mp4'))
            print(f'\n生成的视频片段: {len(clips)}个')
            for clip in clips[:10]:
                size_mb = clip.stat().st_size / 1024 / 1024
                print(f'  {clip.name}: {size_mb:.2f} MB')

if __name__ == '__main__':
    import sys
    project_id = sys.argv[1] if len(sys.argv) > 1 else 'a9e1527c-13a2-496d-a06a-5a80b3c5648e'
    track_project(project_id)
