# 开始提取切片
print('\n🚀 开始提取切片...')
successful_clips, _ = processor.batch_extract_clips(input_video_path, clips_data)

print(f'\n✅ 提取完成！成功生成 {len(successful_clips)} 个切片')
for clip in successful_clips:
    print(f'   - {clip.name}')