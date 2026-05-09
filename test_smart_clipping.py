import sys
import os
from pathlib import Path

project_root = Path('.')
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

from backend.utils.video_processor import VideoProcessor
from backend.utils.hook_extractor import HookExtractor
from backend.utils.smart_clip_generator import SmartClipGenerator

# 测试视频文件路径
input_video_path = Path(r'E:\直播切片项目\output\20260420_新录制\clip_001_product_0s-708s.mp4')

# 输出目录
output_dir = Path('test_output_smart')
clips_dir = output_dir / 'clips'
collections_dir = output_dir / 'collections'

# 确保目录存在
clips_dir.mkdir(parents=True, exist_ok=True)
collections_dir.mkdir(parents=True, exist_ok=True)

print(f'📹 测试视频文件: {input_video_path}')
print(f'📁 输出目录: {output_dir}')

# 检查视频文件是否存在
if not input_video_path.exists():
    print(f'❌ 错误：视频文件不存在: {input_video_path}')
    sys.exit(1)

# ========== 测试1: 钩子提取器 ==========
print('\n' + '='*60)
print('🎯 测试1: 钩子提取器')
print('='*60)

hook_extractor = HookExtractor()

# 测试示例文本
test_texts = [
    '今天给大家分享一个超级实用的小技巧，看完你一定会感谢我！',
    '你知道吗？90%的人都不知道这个秘密',
    '如果你还在用传统方法，那你就OUT了',
    '这个产品到底好不好用？让我来告诉你真实体验',
    '注意看，这个男人叫小帅...',
]

for text in test_texts:
    hooks = hook_extractor.extract_hooks(text)
    if hooks:
        best_hook = hooks[0]
        print(f'📝 文本: "{text[:30]}..."')
        print(f'   检测到钩子类型: {best_hook["type"]}')
        print(f'   钩子内容: {best_hook["content"]}')
        print(f'   评分: {best_hook["score"]:.3f}')
    else:
        print(f'📝 文本: "{text[:30]}..."')
        print('   未检测到钩子')
    print()

# ========== 测试2: 智能切片生成器 ==========
print('\n' + '='*60)
print('🎯 测试2: 智能切片生成器')
print('='*60)

smart_generator = SmartClipGenerator()

# 模拟话题数据
topics = [
    {
        'id': 'topic_1',
        'outline': '介绍产品的核心功能',
        'start_time': '00:00:10.000',
        'end_time': '00:01:30.000'
    },
    {
        'id': 'topic_2', 
        'outline': '演示产品使用方法',
        'start_time': '00:01:30.000',
        'end_time': '00:03:00.000'
    },
    {
        'id': 'topic_3',
        'outline': '用户真实反馈分享',
        'start_time': '00:03:00.000',
        'end_time': '00:04:30.000'
    }
]

# 模拟SRT字幕数据（使用正确的字段名：start_time, end_time）
srt_data = [
    {'start_time': '00:00:00.000', 'end_time': '00:00:03.000', 'text': '今天给大家带来一款非常好用的产品'},
    {'start_time': '00:00:03.000', 'end_time': '00:00:06.000', 'text': '相信很多朋友都有这样的困扰'},
    {'start_time': '00:00:06.000', 'end_time': '00:00:10.000', 'text': '别着急，看完这个视频你就知道解决方案'},
    {'start_time': '00:00:10.000', 'end_time': '00:00:15.000', 'text': '首先我们来看它的核心功能'},
    {'start_time': '00:00:15.000', 'end_time': '00:00:25.000', 'text': '这个产品采用了最新的技术，性能非常出色'},
    {'start_time': '00:00:25.000', 'end_time': '00:00:35.000', 'text': '它可以帮助你节省大量的时间和精力'},
    {'start_time': '00:01:30.000', 'end_time': '00:01:35.000', 'text': '接下来我给大家演示一下具体的使用方法'},
    {'start_time': '00:01:35.000', 'end_time': '00:01:50.000', 'text': '操作非常简单，只需要三步就可以完成'},
    {'start_time': '00:03:00.000', 'end_time': '00:03:05.000', 'text': '很多用户使用后都给出了好评'},
    {'start_time': '00:03:05.000', 'end_time': '00:03:15.000', 'text': '这款产品真的值得入手，性价比很高'},
    {'start_time': '00:03:20.000', 'end_time': '00:03:30.000', 'text': '现在购买还有优惠活动，点击下方链接'},
    {'start_time': '00:04:00.000', 'end_time': '00:04:10.000', 'text': '购物车直接下单，记得领优惠券'},
]

# 提取产品卖点（使用正确的方法名）
product_pitches = smart_generator.extract_all_product_pitches(srt_data)
print(f'✅ 提取到 {len(product_pitches)} 个产品卖点:')
for pitch in product_pitches:
    start_sec = smart_generator._time_to_seconds(pitch['start_time'])
    print(f'   - [{start_sec:.1f}s] {pitch["text"][:40]}... (置信度: {pitch["confidence"]:.2f})')

# 生成智能切片
smart_clips = smart_generator.generate_clips(topics, srt_data)
print(f'\n✅ 生成 {len(smart_clips)} 个智能切片:')
for clip in smart_clips:
    print(f'\n   🎬 切片: {clip["topic_title"]}')
    print(f'      时间: {clip["start_time"]} - {clip["end_time"]}')
    if clip['hook']:
        print(f'      🎣 钩子: {clip["hook"]["hook_type"]} - {clip["hook"]["text"]}')
    if clip['product_pitch']:
        print(f'      🛍️ 产品: {clip["product_pitch"]["text"][:30]}...')

# ========== 测试3: 视频处理器功能 ==========
print('\n' + '='*60)
print('🎯 测试3: 视频处理器功能')
print('='*60)

processor = VideoProcessor(clips_dir=str(clips_dir), collections_dir=str(collections_dir))

# 测试切片提取
test_clips = [
    {'id': 'test_1', 'title': '开场钩子', 'start_time': '00:00:00', 'end_time': '00:00:15'},
    {'id': 'test_2', 'title': '核心话题', 'start_time': '00:00:15', 'end_time': '00:01:00'},
    {'id': 'test_3', 'title': '产品介绍', 'start_time': '00:03:30', 'end_time': '00:04:30'},
]

print('🚀 开始提取测试切片...')
try:
    successful_clips = processor.batch_extract_clips(input_video_path, test_clips)
    print(f'✅ 成功提取 {len(successful_clips)} 个切片')
    for clip in successful_clips:
        print(f'   - {clip.name}')
except Exception as e:
    print(f'❌ 切片提取失败: {e}')

# 测试自适应拼接
if len(successful_clips) >= 2:
    print('\n🚀 测试自适应拼接...')
    output_collection = collections_dir / 'test_collection.mp4'
    try:
        success = processor.create_collection_adaptive(successful_clips, output_collection, use_transition=False)
        if success:
            print(f'✅ 自适应拼接成功: {output_collection}')
        else:
            print('❌ 自适应拼接失败')
    except Exception as e:
        print(f'❌ 拼接失败: {e}')

print('\n' + '='*60)
print('🎉 所有测试完成！')
print('='*60)