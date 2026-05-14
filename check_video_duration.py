
import os
import subprocess

clips_dir = r"E:\ClipProject\autoclip-main1\autoclip-main\data\projects\4402fd35-e134-45a4-81d7-a2440b562a8d\output\clips"

# 获取所有视频文件
video_files = [f for f in os.listdir(clips_dir) if f.endswith(".mp4")]

print("视频文件实际时长检测:")
print("-" * 80)

for video_file in video_files:
    video_path = os.path.join(clips_dir, video_file)
    
    # 使用 ffprobe 获取视频时长
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            import json
            info = json.loads(result.stdout)
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    duration = float(stream.get("duration", 0))
                    print(f"文件: {video_file}")
                    print(f"实际时长: {duration:.2f} 秒")
                    print("-" * 80)
    except Exception as e:
        print(f"获取 {video_file} 时长失败: {e}")
        print("-" * 80)
