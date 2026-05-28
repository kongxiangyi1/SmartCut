"""
重新处理项目 - 测试修复后的流程
"""

import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

async def reprocess_project(project_id: str):
    """重新处理指定项目"""
    from backend.services.simple_pipeline_adapter import SimplePipelineAdapter
    from backend.core.path_utils import get_project_directory
    
    print(f"🚀 开始重新处理项目: {project_id}")
    
    # 获取项目路径
    project_dir = get_project_directory(project_id)
    video_path = project_dir / "raw" / "input.mp4"
    
    if not video_path.exists():
        print(f"❌ 视频文件不存在: {video_path}")
        return
    
    print(f"📹 视频路径: {video_path}")
    
    # 创建适配器并处理
    adapter = SimplePipelineAdapter(project_id, f"reprocess-{project_id[:8]}")
    
    try:
        result = await adapter.process_project_sync(str(video_path), None)
        print(f"\n✅ 处理完成!")
        print(f"结果: {result}")
    except Exception as e:
        print(f"\n❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 使用最新上传的项目
    project_id = "52f81391-ee93-4fb8-8f07-e1c8df90b4ab"
    asyncio.run(reprocess_project(project_id))