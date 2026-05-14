"""
修复数据库中切片的时长数据
从 JSON 文件读取精确的 duration 值并更新数据库
"""

import sqlite3
import json
from pathlib import Path

def fix_clip_times():
    project_id = "b0d4c113-3a61-4df7-a7f0-cc03759c3dc6"
    db_path = r"E:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db"
    json_path = Path(rf"E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\metadata\clips_metadata.json")
    
    # 读取 JSON 文件
    with open(json_path, 'r', encoding='utf-8') as f:
        clips_data = json.load(f)
    
    print(f"从 JSON 文件加载了 {len(clips_data)} 个切片")
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    updated_count = 0
    for clip in clips_data:
        clip_id = clip['id']
        duration = clip.get('duration', 0)
        start_time_str = clip.get('start_time', '00:00:00,000')
        end_time_str = clip.get('end_time', '00:00:00,000')
        
        # 转换时间字符串为秒数
        def parse_time(time_str):
            time_str = time_str.replace(',', '.')
            parts = time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds_parts = parts[2].split('.')
            seconds = int(seconds_parts[0])
            milliseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
            return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
        
        start_time = parse_time(start_time_str)
        end_time = parse_time(end_time_str)
        
        # 更新数据库
        cursor.execute('''
            UPDATE clips
            SET start_time = ?, end_time = ?, duration = ?
            WHERE project_id = ? AND id = ?
        ''', (start_time, end_time, duration, project_id, clip_id))
        
        if cursor.rowcount > 0:
            updated_count += 1
            print(f"更新切片 {clip_id}: duration={duration:.3f}s")
        else:
            print(f"未找到切片 {clip_id}")
    
    conn.commit()
    conn.close()
    
    print(f"\n总共更新了 {updated_count} 个切片")

if __name__ == "__main__":
    fix_clip_times()
