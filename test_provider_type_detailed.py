"""
详细测试 API 接口中的 ProviderType 枚举转换
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_provider_type_in_api():
    print("测试 API 接口中的 ProviderType 枚举转换...")
    print("=" * 60)
    
    # 模拟 API 接口中的代码
    from backend.core.llm_providers import ProviderType
    
    # 打印枚举定义
    print("ProviderType 枚举成员:")
    for member in ProviderType:
        print(f"  - {member.name} = '{member.value}'")
    
    print("\n测试前端可能发送的 provider 值:")
    
    # 测试各种可能的输入值
    test_values = [
        "tencent",
        "TENCENT",
        " tencent ",  # 带空格
        "腾讯",  # 中文
        "tencent-test"
    ]
    
    for value in test_values:
        try:
            provider_type = ProviderType(value)
            print(f"✅ '{value}' -> {provider_type}")
        except ValueError as e:
            print(f"❌ '{value}' -> {e}")
    
    # 模拟 API 请求数据
    print("\n模拟 API 请求数据:")
    request_data = {
        "provider": "tencent",
        "api_key": "test-api-key",
        "model_name": "hunyuan-turbos-latest"
    }
    
    print(f"request.provider = '{request_data['provider']}'")
    
    try:
        provider_type = ProviderType(request_data["provider"])
        print(f"✅ 转换成功: {provider_type}")
    except ValueError as e:
        print(f"❌ 转换失败: {e}")
    
    # 测试 test_provider_connection 方法
    print("\n测试 test_provider_connection 方法:")
    from backend.core.llm_manager import get_llm_manager
    
    llm_manager = get_llm_manager()
    
    try:
        provider_type = ProviderType("tencent")
        success = llm_manager.test_provider_connection(
            provider_type,
            "sk-S2XVtNSX55yXTXSGF8TdTkV8y0bCC2XakcM0iEUsmGy9c3EE",
            "hunyuan-turbos-latest"
        )
        print(f"✅ test_provider_connection 成功: {success}")
    except Exception as e:
        print(f"❌ test_provider_connection 失败: {e}")

if __name__ == "__main__":
    test_provider_type_in_api()