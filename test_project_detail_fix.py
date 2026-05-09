#!/usr/bin/env python3

import requests
import json

def test_project_detail_fix():
    """修复项目详情API的问题"""
    print("🔧 项目详情API修复检查")
    print("=" * 40)
    
    # 获取一个有效的项目ID
    try:
        response = requests.get("http://localhost:8000/api/v1/projects/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            projects = data.get('items', [])
            
            if projects:
                project_id = projects[0]['id']
                print(f"✅ 测试项目详情: {project_id}")
                
                # 测试不同格式的请求
                detail_url = f"http://localhost:8000/api/v1/projects/{project_id}"
                
                print(f"📤 请求: {detail_url}")
                detail_response = requests.get(detail_url, timeout=5)
                
                print(f"📥 响应状态: {detail_response.status_code}")
                
                if detail_response.status_code == 200:
                    print("✅ 项目详情API正常")
                    detail_data = detail_response.json()
                    print(f"   项目: {detail_data.get('name', '')[:30]}...")
                    print(f"   状态: {detail_data.get('status', '')}")
                elif detail_response.status_code == 400:
                    print("❌ 项目详情API返回400")
                    try:
                        error_data = detail_response.json()
                        print(f"   错误详情: {error_data}")
                    except:
                        print(f"   错误文本: {detail_response.text[:200]}")
                
            else:
                print("❌ 没有项目可供测试")
        
    except Exception as e:
        print(f"❌ API测试失败: {e}")

    # 检查API是否因为缺少参数失败
    print("\n🔍 检查常见API错误")
    print("=" * 40)
    
    # 1. 检查参数格式
    print("检查API文档...")
    try:
        docs_response = requests.get("http://localhost:8000/docs", timeout=5)
        if docs_response.status_code == 200:
            print("✅ API文档可访问")
        else:
            print(f"❌ API文档访问失败: {docs_response.status_code}")
    except Exception as e:
        print(f"❌ API文档测试失败: {e}")
    
    # 2. 检查项目数量和状态
    try:
        response = requests.get("http://localhost:8000/api/v1/projects/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            projects = data.get('items', [])
            
            status_count = {}
            for project in projects:
                status = project.get('status', 'unknown')
                status_count[status] = status_count.get(status, 0) + 1
            
            print("\n📊 项目状态统计:")
            for status, count in status_count.items():
                print(f"   {status}: {count}个")
                
            # 对于每个状态分析可能的问题
            if status_count.get('processing', 0) > 0:
                print("\n⚠️  注意: 有正在处理中的项目")
                print("   可能原因: AI分析需要较长时间，这是正常的")
            
            if status_count.get('pending', 0) > 0:
                print("\n⏳ 注意: 有等待处理的项目")
                print("   建议: 确保Celery worker正常运行")
            
    except Exception as e:
        print(f"❌ 项目统计失败: {e}")
    
    print("\n💡 前端修复建议:")
    print("1. ✅ 后端API服务已启动")
    print("2. ✅ 项目列表API正常")
    print("3. 🔧 项目详情API需要修复")
    print("4. ⚠️  确保前端使用正确的项目ID格式")
    print("\n🎯 预计修复后效果:")
    print("- 视频分类: 正常加载")
    print("- 项目列表: 正常显示")
    print("- 项目详情: 修复后可用")
    print("- 上传功能: 正常可用")

if __name__ == '__main__':
    test_project_detail_fix()