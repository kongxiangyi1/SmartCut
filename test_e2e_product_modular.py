"""
产品介绍模块化 - 端到端测试
使用现有项目数据测试Step2产品模块化功能
"""
import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from backend.pipeline.step2_timeline import TimelineExtractor
from backend.core.shared_config import METADATA_DIR

def test_step2_with_product_modular():
    """测试Step2与产品模块化集成"""
    print("="*60)
    print("产品介绍模块化 - 端到端测试")
    print("="*60)

    # 使用现有项目
    project_id = "8dd8d5ba-717c-4232-b165-b0cfd8de941d"
    project_dir = Path(__file__).parent / "data" / "projects" / project_id
    metadata_dir = project_dir / "metadata"

    print(f"\n测试项目: {project_id}")
    print(f"元数据目录: {metadata_dir}")

    # 检查必要的文件
    outline_path = metadata_dir / "step1_outline.json"
    srt_chunks_dir = metadata_dir / "step1_srt_chunks"

    if not outline_path.exists():
        print(f"❌ 大纲文件不存在: {outline_path}")
        return False

    if not srt_chunks_dir.exists():
        print(f"❌ SRT块目录不存在: {srt_chunks_dir}")
        return False

    print(f"✅ 大纲文件存在: {outline_path}")
    print(f"✅ SRT块目录存在: {srt_chunks_dir}")

    # 创建TimelineExtractor
    extractor = TimelineExtractor(metadata_dir=metadata_dir)

    # 加载大纲
    import json
    with open(outline_path, 'r', encoding='utf-8') as f:
        outlines = json.load(f)

    print(f"\n大纲数量: {len(outlines)}")

    # 执行时间线提取（包含产品模块化）
    print("\n开始执行Step2（带产品模块化）...")
    print("-"*40)

    try:
        timeline_data = extractor.extract_timeline(outlines)

        print(f"\n✅ Step2执行成功!")
        print(f"   生成时间线片段数: {len(timeline_data)}")

        # 统计产品模块化结果
        product_intro_count = 0
        high_reuse_count = 0
        total_reuse_value = 0.0

        for item in timeline_data:
            segment_type = item.get('segment_type', 'unknown')
            reuse_value = item.get('reuse_value', 0.0)

            if segment_type == 'product_intro':
                product_intro_count += 1
            if reuse_value >= 0.6:
                high_reuse_count += 1
            total_reuse_value += reuse_value

        print(f"\n📊 产品模块化统计:")
        print(f"   - 产品介绍片段数: {product_intro_count}/{len(timeline_data)}")
        print(f"   - 高复用价值片段数: {high_reuse_count}")
        print(f"   - 平均复用价值: {total_reuse_value/len(timeline_data):.2f}" if timeline_data else "   - 平均复用价值: N/A")

        # 显示每个片段的详情
        print(f"\n📋 片段详情:")
        print("-"*60)
        for item in timeline_data[:5]:  # 只显示前5个
            outline = item.get('outline', '未知')
            if isinstance(outline, dict):
                title = outline.get('title', '未知')
            else:
                title = str(outline)

            segment_type = item.get('segment_type', 'unknown')
            reuse_value = item.get('reuse_value', 0.0)
            segments = item.get('segments', [])
            reusable_clips = item.get('reusable_clips', [])

            print(f"\n片段 {item.get('id')}: {title[:30]}...")
            print(f"   类型: {segment_type}, 复用价值: {reuse_value:.2f}")
            print(f"   子片段数: {len(segments)}, 可复用片段数: {len(reusable_clips)}")

            # 显示子片段
            for seg in segments[:3]:  # 最多显示3个
                print(f"     - [{seg.get('type')}] {seg.get('start'):.1f}s-{seg.get('end'):.1f}s, 复用价值: {seg.get('reuse_value', 0):.2f}")

        # 保存结果
        output_path = metadata_dir / "step2_timeline_with_product.json"
        extractor.save_timeline(timeline_data, output_path)
        print(f"\n✅ 结果已保存到: {output_path}")

        return True

    except Exception as e:
        print(f"\n❌ Step2执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_step2_with_product_modular()

    print("\n" + "="*60)
    if success:
        print("✅ 端到端测试通过!")
    else:
        print("❌ 端到端测试失败!")
        sys.exit(1)
    print("="*60)