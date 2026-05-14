
"""
测试自动线程数计算功能
"""

import sys
from pathlib import Path

# 添加后端路径
backend_path = Path(__file__).parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

sys.path.insert(0, str(Path(__file__).parent))

from backend.utils.video_processor import VideoProcessor


def test_auto_threads():
    """测试自动线程数计算"""
    
    # 创建视频处理器（使用临时目录）
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = VideoProcessor(
            clips_dir=str(Path(tmpdir) / "clips"),
            collections_dir=str(Path(tmpdir) / "collections")
        )
        
        # 测试不同切片数量下的线程数计算
        test_cases = [1, 2, 4, 8, 16, 32]
        
        print("=" * 60)
        print("自动线程数计算测试")
        print("=" * 60)
        
        for clip_count in test_cases:
            threads = processor._calculate_optimal_threads(clip_count)
            print(f"切片数量: {clip_count:2d} -> 最优线程数: {threads:2d}")
        
        print("\n测试完成！")


if __name__ == "__main__":
    test_auto_threads()
