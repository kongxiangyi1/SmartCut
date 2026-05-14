
"""
并行视频切片提取测试脚本
测试串行和并行提取的性能对比
"""

import time
import logging
from pathlib import Path

# 设置日志级别
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 添加后端路径
import sys
backend_path = Path(__file__).parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# 先修复相对导入问题
sys.path.insert(0, str(Path(__file__).parent))

from backend.utils.video_processor import VideoProcessor


def test_parallel_extraction():
    """测试并行提取性能"""
    
    # 配置
    input_video = Path(r"E:\ClipProject\autoclip-main1\autoclip-main\data\projects\4402fd35-e134-45a4-81d7-a2440b562a8d\input\video.mp4")
    clips_dir = Path(r"E:\ClipProject\autoclip-main1\autoclip-main\data\projects\4402fd35-e134-45a4-81d7-a2440b562a8d\output\clips_test")
    collections_dir = Path(r"E:\ClipProject\autoclip-main1\autoclip-main\data\projects\4402fd35-e134-45a4-81d7-a2440b562a8d\output\collections")
    
    # 确保输出目录存在
    clips_dir.mkdir(parents=True, exist_ok=True)
    
    # 示例切片数据（从实际项目中提取）
    clips_data = [
        {"id": "1", "title": "测试片段1", "start_time": "00:00:00,210", "end_time": "00:01:34,328"},
        {"id": "2", "title": "测试片段2", "start_time": "00:01:34,328", "end_time": "00:06:54,750"},
        {"id": "3", "title": "测试片段3", "start_time": "00:06:54,750", "end_time": "00:10:38,655"},
        {"id": "4", "title": "测试片段4", "start_time": "00:10:38,655", "end_time": "00:11:47,895"},
    ]
    
    # 创建视频处理器
    processor = VideoProcessor(
        clips_dir=str(clips_dir),
        collections_dir=str(collections_dir)
    )
    
    # 进度回调函数
    def progress_callback(completed: int, total: int, clip_id: str, success: bool):
        progress = (completed / total) * 100
        status = "✓" if success else "✗"
        print(f"\r进度: [{completed}/{total}] {progress:.1f}% - {status} 切片 {clip_id}", end="")
    
    print("=" * 60)
    print("并行视频切片提取测试")
    print("=" * 60)
    
    # 测试1：串行提取
    print("\n[测试1] 串行提取")
    print("-" * 40)
    start_time = time.time()
    successful_clips_seq = processor.batch_extract_clips(
        input_video, clips_data,
        apply_silence_processing=False  # 禁用静音处理以专注测试提取速度
    )
    seq_time = time.time() - start_time
    print(f"\n串行提取完成，耗时: {seq_time:.2f}秒，成功: {len(successful_clips_seq)}个")
    
    # 清理测试输出
    for clip_path in clips_dir.glob("*.mp4"):
        clip_path.unlink()
    
    # 测试2：并行提取（4线程）
    print("\n[测试2] 并行提取（4线程）")
    print("-" * 40)
    start_time = time.time()
    successful_clips_parallel = processor.batch_extract_clips_parallel(
        input_video, clips_data,
        apply_silence_processing=False,
        max_workers=4,
        progress_callback=progress_callback
    )
    parallel_time_4 = time.time() - start_time
    print(f"\n并行提取完成，耗时: {parallel_time_4:.2f}秒，成功: {len(successful_clips_parallel)}个")
    
    # 清理测试输出
    for clip_path in clips_dir.glob("*.mp4"):
        clip_path.unlink()
    
    # 测试3：并行提取（8线程）
    print("\n[测试3] 并行提取（8线程）")
    print("-" * 40)
    start_time = time.time()
    successful_clips_parallel_8 = processor.batch_extract_clips_parallel(
        input_video, clips_data,
        apply_silence_processing=False,
        max_workers=8,
        progress_callback=progress_callback
    )
    parallel_time_8 = time.time() - start_time
    print(f"\n并行提取完成，耗时: {parallel_time_8:.2f}秒，成功: {len(successful_clips_parallel_8)}个")
    
    # 清理测试输出
    for clip_path in clips_dir.glob("*.mp4"):
        clip_path.unlink()
    
    # 计算加速比
    print("\n" + "=" * 60)
    print("性能对比结果")
    print("=" * 60)
    print(f"串行提取耗时:     {seq_time:.2f}秒")
    print(f"并行提取(4线程):  {parallel_time_4:.2f}秒")
    print(f"并行提取(8线程):  {parallel_time_8:.2f}秒")
    if seq_time > 0:
        print(f"\n加速比(4线程):    {(seq_time / parallel_time_4):.2f}x")
        print(f"加速比(8线程):    {(seq_time / parallel_time_8):.2f}x")
    
    # 删除测试目录
    clips_dir.rmdir()
    
    print("\n测试完成！")


if __name__ == "__main__":
    test_parallel_extraction()
