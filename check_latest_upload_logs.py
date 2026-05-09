#!/usr/bin/env python3

import requests
import json
import time
from datetime import datetime

def check_upload_logs():
    """检查最新上传文件的处理日志"""
    print("📋 最新上传文件日志检查")
    print("=" * 60)
    
    try:
        # 获取所有项目
        response = requests.get("http://localhost:8000/api/v1/projects/", timeout=10)
        
        if response.status_code != 200:
            print(f"❌ API访问失败: {response.status_code}")
            return
        
        data = response.json()
        projects = sorted(data['items'], key=lambda x: x['created_at'], reverse=True)
        
        print(f"📊 总共 {len(projects)} 个项目\n")
        
        # 找到最新的项目（上传的）
        if not projects:
            print("❌ 没有找到任何项目")
            return
            
        latest = projects[0]
        print(f"🆕 最新上传的项目:")
        print(f"   ID: {latest['id']}")
        print(f"   名称: {latest['name'][:50]}")
        print(f"   状态: {latest['status']}")
        print(f"   类型: {latest['project_type']}")
        print(f"   创建时间: {latest['created_at']}")
        print(f"   更新时间: {latest['updated_at']}")
        print(f"   片段数: {latest['total_clips']}")
        print(f"   合集数: {latest['total_collections']}")
        
        # 分析状态
        status = latest['status']
        if status == 'completed':
            print(f"   ✅ 处理完成: 可以查看{latests.get('total_clips', 0)}个片段和{latests.get('total_collections', 0)}个合集")
        elif status == 'processing':
            print(f"   🔄 正在处理: AI正在分析视频内容...预计15-30分钟")
        elif status == 'pending':
            print(f"   ⏳ 等待处理: 项目在队列中等待Celery worker处理")
        elif status == 'failed':
            print(f"   ❌ 处理失败: 需要查看详细错误日志")
        
        # 检查是否有上传的文件
        print(f"\n📁 文件状态检查:")
        import os
        from pathlib import Path
        
        project_id = latest['id']
        project_dir = Path('data') / 'projects' / project_id / 'raw'
        
        if project_dir.exists():
            files = list(project_dir.glob('*'))
            print(f"   ✅ 项目文件夹存在: {project_dir}")
            print(f"   📂 文件数量: {len(files)}")
            
            video_files = [f for f in files if f.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv']]
            if video_files:
                for video_file in video_files:
                    size_mb = video_file.stat().st_size / (1024*1024)
                    print(f"   🎬 视频文件: {video_file.name} ({size_mb:.1f} MB)")
            else:
                print(f"   ❌ 未找到视频文件")
                
            # 字幕文件
            srt_files = [f for f in files if f.suffix.lower() in ['.srt', '.vtt', '.txt']]
            if srt_files:
                for srt_file in srt_files:
                    print(f"   📝 字幕文件: {srt_file.name}")
            else:
                print(f"   🔄 无字幕文件: 将使用AI自动生成")
        else:
            print(f"   ❌ 项目文件夹不存在: {project_dir}")
        
        # 检查处理日志
        print(f"\n📋 处理状态详细日志:")
        
        # 项目详情包含更多信息
        try:
            detail_response = requests.get(f"http://localhost:8000/api/v1/projects/{project_id}", timeout=10)
            if detail_response.status_code == 200:
                detail_data = detail_response.json()
                
                # 检查是否有处理设置信息
                settings = detail_data.get('settings', {})
                if settings:
                    print(f"   ⚙️  处理设置: {len(settings)} 项配置")
                    for key, value in list(settings.items())[:3]:  # 显示前3个
                        print(f"      {key}: {value}")
                
                # 显示其他有用信息
                if detail_data.get('source_url'):
                    print(f"   🌐 源URL: {detail_data['source_url']}")
                if detail_data.get('source_file'):
                    print(f"   📁 源文件: {detail_data['source_file']}")
                    
            else:
                print(f"   ❌ 无法获取项目详情: {detail_response.status_code}")
                
        except Exception as e:
            print(f"   ❌ 获取详情失败: {e}")
        
        # 检查处理中的项目
        processing_projects = [p for p in projects if p['status'] == 'processing']
        if processing_projects:
            print(f"\n🔄 正在处理的项目 ({len(processing_projects)}):")
            for proj in processing_projects:
                ago = time_ago(proj['updated_at'])
                print(f"   • {proj['name'][:30]}... - 最后更新: {ago}")
        
        # 检查等待的项目
        pending_projects = [p for p in projects if p['status'] == 'pending']
        if pending_projects:
            print(f"\n⏳ 等待处理的项目 ({len(pending_projects)}):")
            for proj in pending_projects:
                ago = time_ago(proj['created_at'])
                print(f"   • {proj['name'][:30]}... - 等待时间: {ago}")
        
        print(f"\n💡 诊断建议:")
        
        # 根据状态给出建议
        if status == 'pending':
            print(f"   🔧 项目在等待队列中，建议:")
            print(f"      - 检查Celery worker是否运行正常")
            print(f"      - 如果等待时间过长，可手动提交处理")
        elif status == 'processing':
            print(f"   🔧 项目正在处理中，建议:")
            print(f"      - 耐心等待AI分析完成（通常15-30分钟）")
            print(f"      - 可以定期刷新查看进度")
        elif status == 'completed':
            print(f"   ✅ 项目处理完成，可以:")
            print(f"      - 查看生成的视频片段")
            print(f"      - 查看智能推荐的合集")
        elif status == 'failed':
            print(f"   ❌ 项目处理失败，建议:")
            print(f"      - 查看具体错误日志")
            print(f"      - 重新试处理")
        
        print(f"\n🎯 总结:")
        print(f"   📈 项目总数: {len(projects)}")
        print(f"   ✅ 已完成: {len([p for p in projects if p['status'] == 'completed'])}")
        print(f"   🔄 处理中: {len(processing_projects)}")
        print(f"   ⏳ 等待中: {len(pending_projects)}")
        print(f"   ❌ 失败: {len([p for p in projects if p['status'] == 'failed'])}")
        
    except Exception as e:
        print(f"❌ 日志检查失败: {e}")
        import traceback
        traceback.print_exc()

def time_ago(timestamp_str):
    """将时间戳转换为相对时间"""
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now()
        diff = now - timestamp.replace(tzinfo=None)
        
        if diff.days > 0:
            return f"{diff.days}天前"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}小时前"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}分钟前"
        else:
            return "刚刚"
    except:
        return "未知"

if __name__ == '__main__':
    check_upload_logs()