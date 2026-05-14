
import os

clips_dir = r"E:\ClipProject\autoclip-main1\autoclip-main\data\projects\4402fd35-e134-45a4-81d7-a2440b562a8d\output\clips"

# 获取所有视频文件
video_files = [f for f in os.listdir(clips_dir) if f.endswith(".mp4")]

print("视频文件列表:")
print("-" * 80)

for video_file in video_files:
    video_path = os.path.join(clips_dir, video_file)
    print(f"文件名: {video_file}")
    print(f"完整路径: {video_path}")
    print(f"文件大小: {os.path.getsize(video_path) / (1024 * 1024):.2f} MB")
    print("-" * 80)
