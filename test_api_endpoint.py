"""
测试后端 API /settings/test-api-key 接口
"""
import sys
import os
import requests

def test_api_key_endpoint():
    print("正在测试 /settings/test-api-key 接口...")
    
    # API 端点
    url = "http://localhost:8000/api/v1/settings/test-api-key"
    
    # 测试数据
    payload = {
        "provider": "tencent",
        "api_key": "sk-S2XVtNSX55yXTXSGF8TdTkV8y0bCC2XakcM0iEUsmGy9c3EE",
        "model_name": "hunyuan-turbos-latest"
    }
    
    try:
        print(f"发送请求到: {url}")
        print(f"请求数据: {payload}")
        
        response = requests.post(url, json=payload)
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ API 接口测试成功！")
                return True
            else:
                print(f"❌ API 接口测试失败: {result.get('error')}")
                return False
        else:
            print(f"❌ 请求失败，状态码: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请确保后端服务正在运行")
        return False
    except Exception as e:
        print(f"❌ 测试过程中出现异常：{str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 测试 API Key 接口")
    print("=" * 60)
    
    success = test_api_key_endpoint()
    
    print("=" * 60)
    print("测试结果:", "✅ 成功" if success else "❌ 失败")
    
    sys.exit(0 if success else 1)