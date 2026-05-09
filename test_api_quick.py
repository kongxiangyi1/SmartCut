#!/usr/bin/env python3

import requests
import json

def test_api_endpoints():
    """快速测试后端API端点"""
    print("🔍 测试后端API端点")
    print("=" * 40)
    
    base_url = "http://localhost:8000"
    endpoints = [
        ("Root", "/"),
        ("API Docs", "/docs"),
        ("Projects", "/api/v1/projects/"),
        ("Settings", "/api/v1/settings")
    ]
    
    for name, path in endpoints:
        url = base_url + path
        try:
            response = requests.get(url, timeout=5)
            print(f"✅ {name}: {response.status_code}")
            
            if name == "Projects" and response.status_code == 200:
                data = response.json()
                projects = data.get('items', [])
                print(f"   📊 项目数量: {len(projects)}")
                
                if projects:
                    print("   📋 项目列表:")
                    for i, proj in enumerate(projects[:5]):
                        name = proj.get('name', '')[:25]
                        status = proj.get('status', 'unknown')
                        project_type = proj.get('project_type', 'unknown')
                        print(f"      {i+1}. {name}... - {status} ({project_type})")
                        
        except Exception as e:
            print(f"❌ {name}: {e}")
    
    print("\n🎯 前端常见API测试")
    
    # 测试前端可能需要的特定API
    try:
        # 获取项目详情测试
        response = requests.get(f"{base_url}/api/v1/projects/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('items'):
                project_id = data['items'][0]['id']
                print(f"✅ 获取项目详情: {base_url}/api/v1/projects/{project_id}")
                
                detail_response = requests.get(f"{base_url}/api/v1/projects/{project_id}", timeout=5)
                if detail_response.status_code == 200:
                    print(f"   ✅ 项目详情API正常")
                else:
                    print(f"   ❌ 项目详情API: {detail_response.status_code}")
            
    except Exception as e:
        print(f"❌ 项目详情测试: {e}")
    
    print("\n💡 修复建议:")
    print("如果前端仍报错，可能是:")
    print("1. 前端服务缓存问题 - 请刷新或重启前端")
    print("2. CORS配置问题 - 检查后端CORS设置")
    print("3. 前端配置问题 - 检查API地址配置")
    print("4. 浏览器缓存 - 清除缓存或硬刷新(Ctrl+F5)")

if __name__ == '__main__':
    test_api_endpoints()