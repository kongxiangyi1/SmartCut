"""
直接测试后端的 test_api_key 函数
"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# 直接导入并测试
from backend.api.v1.settings import test_api_key
from backend.api.v1.settings import ApiKeyTestRequest

# 创建测试请求
request = ApiKeyTestRequest(
    provider="tencent",
    api_key="sk-S2XVtNSX55yXTXSGF8TdTkV8y0bCC2XakcM0iEUsmGy9c3EE",
    model_name="hunyuan-turbos-latest"
)

print(f"测试请求数据:")
print(f"  provider: '{request.provider}'")
print(f"  api_key: '{request.api_key[:10]}...'")
print(f"  model_name: '{request.model_name}'")

# 异步调用函数
async def main():
    response = await test_api_key(request)
    print(f"\n响应结果:")
    print(f"  success: {response.success}")
    print(f"  error: {response.error}")

asyncio.run(main())