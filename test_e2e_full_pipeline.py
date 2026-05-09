"""
完整端到端测试 - 使用测试视频文件测试整个视频切片流水线
简化版本：不依赖数据库，直接测试Pipeline功能
"""
import sys
import os
import json
import uuid
from pathlib import Path

project_root = Path('.')
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

from backend.services.simple_pipeline_adapter import create_simple_pipeline_adapter

def run_full_pipeline_test():
    """运行完整的端到端测试"""
    print("\n" + "="*70)
    print("🎬 完整端到端测试 - 视频切片流水线")
    print("="*70)
    
    # 测试视频路径
    input_video_path = r'E:\直播切片项目\output\20260420_新录制\clip_001_product_0s-708s.mp4'
    input_video_path = Path(input_video_path)
    
    print(f"\n📹 测试视频: {input_video_path}")
    
    # 检查视频文件
    if not input_video_path.exists():
        print(f"❌ 错误：视频文件不存在: {input_video_path}")
        return False
    
    # 生成唯一ID
    project_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    
    print(f"\n📋 测试参数:")
    print(f"   项目ID: {project_id[:8]}...")
    print(f"   任务ID: {task_id[:8]}...")
    
    # 创建Pipeline适配器
    print("\n🚀 初始化Pipeline适配器...")
    pipeline_adapter = create_simple_pipeline_adapter(project_id, task_id)
    
    # 执行完整流水线
    print("\n" + "-"*70)
    print("开始执行完整视频处理流水线")
    print("-"*70)
    
    import asyncio
    result = asyncio.run(pipeline_adapter.process_project_sync(str(input_video_path), ""))
    
    print("\n" + "-"*70)
    print("流水线执行结果")
    print("-"*70)
    
    if result["status"] == "succeeded":
        print("✅ 流水线处理成功!")
        
        # 获取项目目录
        from backend.core.path_utils import get_project_directory
        project_dir = get_project_directory(project_id)
        metadata_dir = project_dir / "metadata"
        output_dir = project_dir / "output"
        
        # 打印各步骤结果
        pipeline_result = result["result"]
        
        print(f"\n📊 处理统计:")
        print(f"   - 大纲数量: {len(pipeline_result.get('outlines', []))}")
        print(f"   - 时间线片段: {len(pipeline_result.get('timeline', []))}")
        print(f"   - 高分片段: {len(pipeline_result.get('scored_clips', []))}")
        print(f"   - 带标题片段: {len(pipeline_result.get('titled_clips', []))}")
        print(f"   - 合集数量: {len(pipeline_result.get('collections', []))}")
        
        if pipeline_result.get('video_result'):
            video_result = pipeline_result['video_result']
            print(f"   - 切片数量: {video_result.get('clips_generated', 0)}")
            print(f"   - 合集数量: {video_result.get('collections_generated', 0)}")
        
        # 检查生成的文件
        print("\n📁 生成的文件:")
        
        # 检查元数据文件
        if metadata_dir.exists():
            metadata_files = list(metadata_dir.glob("*.json"))
            for meta_file in metadata_files:
                file_size = meta_file.stat().st_size
                print(f"   - {meta_file.name} ({file_size} bytes)")
        
        # 检查切片文件
        clips_dir = output_dir / "clips"
        if clips_dir.exists():
            clip_files = list(clips_dir.glob("*.mp4"))
            print(f"\n🎥 生成的切片 ({len(clip_files)}个):")
            for clip_file in clip_files:
                file_size_mb = clip_file.stat().st_size / (1024 * 1024)
                print(f"   - {clip_file.name} ({file_size_mb:.2f} MB)")
        
        # 检查合集文件
        collections_dir = output_dir / "collections"
        if collections_dir.exists():
            collection_files = list(collections_dir.glob("*.mp4"))
            print(f"\n📦 生成的合集 ({len(collection_files)}个):")
            for coll_file in collection_files:
                file_size_mb = coll_file.stat().st_size / (1024 * 1024)
                print(f"   - {coll_file.name} ({file_size_mb:.2f} MB)")
        
        # 打印步骤详情
        print("\n📋 步骤详情:")
        
        # Step 1: 大纲
        outlines_file = metadata_dir / "step1_outline.json"
        if outlines_file.exists():
            with open(outlines_file, 'r', encoding='utf-8') as f:
                outlines = json.load(f)
            if outlines:
                print("\n   Step 1 - 大纲提取:")
                for i, outline in enumerate(outlines[:3]):
                    title = outline.get('title', outline.get('outline', '未知'))
                    print(f"      [{i+1}] {title[:40]}...")
        
        # Step 2: 时间线
        timeline_file = metadata_dir / "step2_timeline.json"
        if timeline_file.exists():
            with open(timeline_file, 'r', encoding='utf-8') as f:
                timeline = json.load(f)
            if timeline:
                print("\n   Step 2 - 时间线提取:")
                for i, item in enumerate(timeline[:3]):
                    outline = item.get('outline', {})
                    if isinstance(outline, dict):
                        title = outline.get('title', '未知')
                    else:
                        title = str(outline)
                    segment_type = item.get('segment_type', 'unknown')
                    print(f"      [{i+1}] {title[:30]}... (类型: {segment_type})")
        
        # Step 4: 标题
        titles_file = metadata_dir / "step4_titles.json"
        if titles_file.exists():
            with open(titles_file, 'r', encoding='utf-8') as f:
                titles = json.load(f)
            if titles:
                print("\n   Step 4 - 标题生成:")
                for i, item in enumerate(titles[:3]):
                    title = item.get('generated_title', '无标题')
                    start = item.get('start_time', '未知')
                    end = item.get('end_time', '未知')
                    print(f"      [{i+1}] {title} ({start} - {end})")
        
        print(f"\n🎉 端到端测试完成!")
        print(f"   项目位置: {project_dir}")
        
        return True
        
    else:
        print(f"❌ 流水线处理失败: {result.get('error', '未知错误')}")
        return False

if __name__ == "__main__":
    success = run_full_pipeline_test()
    
    print("\n" + "="*70)
    if success:
        print("✅ 端到端测试通过!")
    else:
        print("❌ 端到端测试失败!")
        sys.exit(1)
    print("="*70)