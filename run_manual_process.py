import sys
import asyncio
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

print(f'🎯 目标项目: {project_id}')
print(f'⏳ 开始完整处理...\n')

data_root = project_root / 'data' / 'projects' / project_id
input_video_path = data_root / 'raw' / 'input.mp4'
input_srt_path = data_root / 'metadata' / 'input.srt'

print(f'📹 视频文件: {input_video_path}')
print(f'📝 字幕文件: {input_srt_path}')

from backend.services.pipeline_adapter import create_pipeline_adapter_sync
from backend.core.database import SessionLocal

db = SessionLocal()
pipeline_adapter = create_pipeline_adapter_sync(db, 'manual_task', project_id)

errors = pipeline_adapter.validate_pipeline_prerequisites()
if errors:
    print(f'❌ 前置条件验证失败: {errors}')
    sys.exit(1)

print('✅ 前置条件验证通过')

result = asyncio.run(pipeline_adapter.process_project(
    input_video_path=str(input_video_path),
    input_srt_path=str(input_srt_path)
))

print(f'\n📊 处理结果: {result}')

if result.get('status') == 'success':
    print('✅ 项目处理成功！')
else:
    print(f'❌ 项目处理失败: {result.get("message")}')
    sys.exit(1)
