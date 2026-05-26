print('🚀 开始提取测试切片...')
try:
    successful_clips, _ = processor.batch_extract_clips(input_video_path, test_clips)
    print(f'✅ 成功提取 {len(successful_clips)} 个切片')
    for clip in successful_clips:
        print(f'   - {clip.name}')
except Exception as e:
    print(f'❌ 切片提取失败: {e}')