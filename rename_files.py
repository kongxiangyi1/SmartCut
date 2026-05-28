"""
重命名切片视频文件，让它们匹配数据库中的video_path
"""
import os
from pathlib import Path

project_id = "6be285fa-31e4-4487-898a-c26b38753af1"

# 构建项目路径
project_path = Path("data/projects") / project_id
clips_dir = project_path / "output" / "clips"

print(f"Checking clips dir: {clips_dir}")
print(f"Exists: {clips_dir.exists()}")

if clips_dir.exists():
    print("\nOriginal files:")
    for file in clips_dir.glob("*.mp4"):
        print(f"  {file.name}")
    
    print("\nRenaming files...")
    
    # 重命名文件
    old_files = [
        ("1_片段_1.mp4", "clip_1_精彩标题_1.mp4"),
        ("2_片段_2.mp4", "clip_2_精彩标题_2.mp4"),
        ("3_片段_3.mp4", "clip_3_精彩标题_3.mp4"),
    ]
    
    for old_name, new_name in old_files:
        old_path = clips_dir / old_name
        new_path = clips_dir / new_name
        
        if old_path.exists():
            print(f"  Renaming {old_name} -> {new_name}")
            try:
                old_path.rename(new_path)
                print(f"  Success!")
            except Exception as e:
                print(f"  Error: {e}")
        else:
            print(f"  File not found: {old_name}")
    
    print("\nFiles after rename:")
    for file in clips_dir.glob("*.mp4"):
        print(f"  {file.name}")
else:
    print("Clips directory not found!")
