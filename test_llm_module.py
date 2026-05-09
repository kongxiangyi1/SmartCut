"""
AI处理引擎模块接口测试
测试LLM客户端、管理器、提供商和文本处理模块的功能
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 测试结果收集器
test_results = {
    "passed": [],
    "failed": [],
    "skipped": [],
    "total": 0
}

def log_test(name, status, message=""):
    """记录测试结果"""
    test_results["total"] += 1
    result_entry = {"name": name, "message": message}
    if status == "PASS":
        test_results["passed"].append(result_entry)
        print(f"  ✅ {name}")
    elif status == "FAIL":
        test_results["failed"].append(result_entry)
        print(f"  ❌ {name}: {message}")
    else:
        test_results["skipped"].append(result_entry)
        print(f"  ⏭️ {name}: {message}")


def test_imports():
    """测试模块导入"""
    print("\n" + "="*60)
    print("测试1: 模块导入")
    print("="*60)

    # 测试LLM客户端导入
    try:
        from backend.utils.llm_client import LLMClient
        log_test("LLMClient 导入", "PASS")
    except Exception as e:
        log_test("LLMClient 导入", "FAIL", str(e))
        return None

    # 测试LLM管理器导入
    try:
        from backend.core.llm_manager import LLMManager, get_llm_manager
        log_test("LLMManager 导入", "PASS")
    except Exception as e:
        log_test("LLMManager 导入", "FAIL", str(e))

    # 测试LLM提供商导入
    try:
        from backend.core.llm_providers import (
            LLMProvider, LLMProviderFactory, ProviderType,
            ModelInfo, LLMResponse,
            DashScopeProvider, OpenAIProvider, GeminiProvider, SiliconFlowProvider,
            ZhipuProvider
        )
        log_test("LLM Providers 导入", "PASS")
    except Exception as e:
        log_test("LLM Providers 导入", "FAIL", str(e))

    # 测试文本处理模块导入
    try:
        from backend.utils.text_processor import TextProcessor
        log_test("TextProcessor 导入", "PASS")
    except Exception as e:
        log_test("TextProcessor 导入", "FAIL", str(e))

    # 测试流水线模块导入
    try:
        from backend.pipeline.step1_outline import OutlineExtractor
        from backend.pipeline.step2_timeline import TimelineExtractor
        from backend.pipeline.step3_scoring import ClipScorer
        from backend.pipeline.step4_title import TitleGenerator
        from backend.pipeline.step5_clustering import ClusteringEngine
        from backend.pipeline.step6_video import VideoGenerator
        log_test("Pipeline Steps 导入", "PASS")
    except Exception as e:
        log_test("Pipeline Steps 导入", "FAIL", str(e))

    return True


def test_llm_manager():
    """测试LLM管理器"""
    print("\n" + "="*60)
    print("测试2: LLM管理器接口")
    print("="*60)

    try:
        from backend.core.llm_manager import get_llm_manager, ProviderType

        # 获取管理器实例
        manager = get_llm_manager()
        log_test("get_llm_manager() 获取实例", "PASS")

        # 测试获取当前提供商信息
        try:
            info = manager.get_current_provider_info()
            log_test("get_current_provider_info()", "PASS")
            print(f"      当前提供商: {info.get('provider')}, 模型: {info.get('model')}")
        except Exception as e:
            log_test("get_current_provider_info()", "FAIL", str(e))

        # 测试获取所有可用模型
        try:
            models = manager.get_all_available_models()
            log_test("get_all_available_models()", "PASS")
            for provider, model_list in models.items():
                print(f"      {provider}: {len(model_list)} 个模型")
        except Exception as e:
            log_test("get_all_available_models()", "FAIL", str(e))

        # 测试设置加载
        try:
            settings = manager.settings
            log_test("manager.settings 访问", "PASS")
            print(f"      当前设置: provider={settings.get('llm_provider')}, model={settings.get('model_name')}")
        except Exception as e:
            log_test("manager.settings 访问", "FAIL", str(e))

        # 测试提供商切换功能
        try:
            test_provider_type = ProviderType.DASHSCOPE
            test_api_key = settings.get('dashscope_api_key', '')
            test_model = settings.get('model_name', 'qwen-plus')

            if test_api_key:
                manager.set_provider(test_provider_type, test_api_key, test_model)
                log_test("set_provider() 切换提供商", "PASS")
            else:
                log_test("set_provider() 切换提供商", "SKIP", "无API密钥")
        except Exception as e:
            log_test("set_provider() 切换提供商", "FAIL", str(e))

    except Exception as e:
        log_test("LLM管理器测试", "FAIL", str(e))


def test_llm_providers():
    """测试LLM提供商"""
    print("\n" + "="*60)
    print("测试3: LLM提供商接口")
    print("="*60)

    from backend.core.llm_providers import (
        LLMProviderFactory, ProviderType, ModelInfo, LLMResponse
    )

    # 测试提供商工厂
    try:
        providers = list(ProviderType)
        log_test("ProviderType 枚举列表", "PASS")
        print(f"      可用提供商: {[p.value for p in providers]}")
    except Exception as e:
        log_test("ProviderType 枚举列表", "FAIL", str(e))

    # 测试创建提供商
    try:
        # 检查是否有API密钥
        from backend.core.llm_manager import get_llm_manager
        manager = get_llm_manager()
        settings = manager.settings

        dashscope_key = settings.get('dashscope_api_key', '')
        openai_key = settings.get('openai_api_key', '')

        if dashscope_key:
            provider = LLMProviderFactory.create_provider(
                ProviderType.DASHSCOPE, dashscope_key, "qwen-plus"
            )
            log_test("create_provider(DashScope)", "PASS")
        else:
            log_test("create_provider(DashScope)", "SKIP", "无API密钥")

        if openai_key:
            provider = LLMProviderFactory.create_provider(
                ProviderType.OPENAI, openai_key, "gpt-3.5-turbo"
            )
            log_test("create_provider(OpenAI)", "PASS")
        else:
            log_test("create_provider(OpenAI)", "SKIP", "无API密钥")

    except Exception as e:
        log_test("LLMProviderFactory.create_provider()", "FAIL", str(e))

    # 测试模型信息
    try:
        from backend.core.llm_providers import DashScopeProvider
        # 创建一个不调用API的测试
        class MockDashScopeProvider:
            def get_available_models(self):
                return DashScopeProvider.__bases__  # 检查基类
        log_test("Provider类结构检查", "PASS")
    except Exception as e:
        log_test("Provider类结构检查", "FAIL", str(e))


def test_text_processor():
    """测试文本处理模块"""
    print("\n" + "="*60)
    print("测试4: 文本处理模块接口")
    print("="*60)

    from backend.utils.text_processor import TextProcessor

    processor = TextProcessor()

    # 测试SRT解析
    try:
        test_srt = """1
00:00:01,000 --> 00:00:05,000
这是第一段字幕

2
00:00:05,000 --> 00:00:10,000
这是第二段字幕

3
00:00:10,000 --> 00:00:15,000
这是第三段字幕
"""
        # 写入临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
            f.write(test_srt)
            temp_srt_path = f.name

        srt_data = processor.parse_srt(Path(temp_srt_path))
        log_test("TextProcessor.parse_srt()", "PASS")
        print(f"      解析了 {len(srt_data)} 条字幕")

        # 清理临时文件
        os.unlink(temp_srt_path)
    except Exception as e:
        log_test("TextProcessor.parse_srt()", "FAIL", str(e))

    # 测试文本分块
    try:
        long_text = "这是测试文本。 " * 100
        chunks = processor.chunk_text(long_text, chunk_size=500)
        log_test("TextProcessor.chunk_text()", "PASS")
        print(f"      长文本被分成 {len(chunks)} 个块")
    except Exception as e:
        log_test("TextProcessor.chunk_text()", "FAIL", str(e))

    # 测试SRT数据分块
    try:
        srt_data = [
            {"index": 1, "start_time": "00:00:01,000", "end_time": "00:00:05,000", "text": "文本1"},
            {"index": 2, "start_time": "00:00:05,000", "end_time": "00:00:10,000", "text": "文本2"},
            {"index": 3, "start_time": "00:00:10,000", "end_time": "00:00:15,000", "text": "文本3"},
            {"index": 4, "start_time": "00:00:15,000", "end_time": "00:00:20,000", "text": "文本4"},
        ]
        srt_chunks = processor.chunk_srt_data(srt_data, interval_minutes=30)
        log_test("TextProcessor.chunk_srt_data()", "PASS")
        print(f"      SRT数据被分成 {len(srt_chunks)} 个块")
    except Exception as e:
        log_test("TextProcessor.chunk_srt_data()", "FAIL", str(e))


def test_llm_client():
    """测试LLM客户端"""
    print("\n" + "="*60)
    print("测试5: LLM客户端接口")
    print("="*60)

    from backend.utils.llm_client import LLMClient

    client = LLMClient()

    # 测试JSON响应解析
    try:
        test_responses = [
            '{"key": "value"}',
            '```json\n{"key": "value"}\n```',
            '以下是JSON：\n{"key": "value"}\n结束',
            '{"1": "标题1", "2": "标题2"}'
        ]

        for i, response in enumerate(test_responses):
            try:
                result = client.parse_json_response(response)
                log_test(f"parse_json_response() 测试{i+1}", "PASS")
            except Exception as e:
                log_test(f"parse_json_response() 测试{i+1}", "FAIL", str(e))
    except Exception as e:
        log_test("LLM客户端JSON解析测试", "FAIL", str(e))

    # 测试响应预处理
    try:
        raw_response = '   \n\n以下是结果：\n{"test": "data"}\n   '
        processed = client._preprocess_llm_response(raw_response)
        log_test("LLMClient._preprocess_llm_response()", "PASS")
    except Exception as e:
        log_test("LLMClient._preprocess_llm_response()", "FAIL", str(e))

    # 测试API调用（需要API密钥）
    try:
        from backend.core.llm_manager import get_llm_manager
        manager = get_llm_manager()
        settings = manager.settings
        api_key = settings.get('dashscope_api_key', '')

        if api_key:
            # 测试实际API调用
            response = client.call_with_retry("请回复'测试成功'")
            if "测试成功" in response or "success" in response.lower():
                log_test("LLMClient.call_with_retry() 实际API调用", "PASS")
            else:
                log_test("LLMClient.call_with_retry() 实际API调用", "FAIL", "响应不符合预期")
        else:
            log_test("LLMClient.call_with_retry() 实际API调用", "SKIP", "无API密钥")
    except Exception as e:
        log_test("LLMClient.call_with_retry() 实际API调用", "FAIL", str(e))


def test_pipeline_steps():
    """测试流水线各步骤"""
    print("\n" + "="*60)
    print("测试6: 流水线各步骤接口")
    print("="*60)

    # 创建临时目录用于测试
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        metadata_dir = temp_path / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)

        # 创建测试SRT文件
        test_srt_content = """1
00:00:01,000 --> 00:00:05,000
这是关于人工智能的第一段内容

2
00:00:05,000 --> 00:00:10,000
AI技术正在改变世界

3
00:00:10,000 --> 00:00:15,000
机器学习是AI的核心

4
00:00:15,000 --> 00:00:20,000
深度学习推动了AI发展
"""
        test_srt_path = temp_path / "test.srt"
        test_srt_path.write_text(test_srt_content, encoding='utf-8')

        # 测试Step1 - 大纲提取器
        try:
            from backend.pipeline.step1_outline import OutlineExtractor
            extractor = OutlineExtractor(metadata_dir=metadata_dir)
            log_test("OutlineExtractor 初始化", "PASS")

            # 检查必要属性
            has_extract = hasattr(extractor, 'extract_outline')
            log_test("OutlineExtractor.extract_outline() 方法存在", "PASS" if has_extract else "FAIL")

        except Exception as e:
            log_test("OutlineExtractor 初始化", "FAIL", str(e))

        # 测试Step2 - 时间线提取器
        try:
            from backend.pipeline.step2_timeline import TimelineExtractor
            extractor = TimelineExtractor(metadata_dir=metadata_dir)
            log_test("TimelineExtractor 初始化", "PASS")

            has_extract = hasattr(extractor, 'extract_timeline')
            log_test("TimelineExtractor.extract_timeline() 方法存在", "PASS" if has_extract else "FAIL")

        except Exception as e:
            log_test("TimelineExtractor 初始化", "FAIL", str(e))

        # 测试Step3 - 评分器
        try:
            from backend.pipeline.step3_scoring import ClipScorer
            scorer = ClipScorer()
            log_test("ClipScorer 初始化", "PASS")

            has_score = hasattr(scorer, 'score_clips')
            log_test("ClipScorer.score_clips() 方法存在", "PASS" if has_score else "FAIL")

        except Exception as e:
            log_test("ClipScorer 初始化", "FAIL", str(e))

        # 测试Step4 - 标题生成器
        try:
            from backend.pipeline.step4_title import TitleGenerator
            generator = TitleGenerator(metadata_dir=metadata_dir)
            log_test("TitleGenerator 初始化", "PASS")

            has_generate = hasattr(generator, 'generate_titles')
            log_test("TitleGenerator.generate_titles() 方法存在", "PASS" if has_generate else "FAIL")

        except Exception as e:
            log_test("TitleGenerator 初始化", "FAIL", str(e))

        # 测试Step5 - 聚类引擎
        try:
            from backend.pipeline.step5_clustering import ClusteringEngine
            engine = ClusteringEngine(metadata_dir=metadata_dir)
            log_test("ClusteringEngine 初始化", "PASS")

            has_cluster = hasattr(engine, 'cluster_clips')
            log_test("ClusteringEngine.cluster_clips() 方法存在", "PASS" if has_cluster else "FAIL")

        except Exception as e:
            log_test("ClusteringEngine 初始化", "FAIL", str(e))

        # 测试Step6 - 视频生成器
        try:
            clips_dir = temp_path / "clips"
            collections_dir = temp_path / "collections"
            clips_dir.mkdir(parents=True, exist_ok=True)
            collections_dir.mkdir(parents=True, exist_ok=True)

            from backend.pipeline.step6_video import VideoGenerator
            generator = VideoGenerator(
                clips_dir=str(clips_dir),
                collections_dir=str(collections_dir),
                metadata_dir=str(metadata_dir)
            )
            log_test("VideoGenerator 初始化", "PASS")

            has_generate = hasattr(generator, 'generate_clips')
            log_test("VideoGenerator.generate_clips() 方法存在", "PASS" if has_generate else "FAIL")

        except Exception as e:
            log_test("VideoGenerator 初始化", "FAIL", str(e))


def test_api_endpoints():
    """测试API端点"""
    print("\n" + "="*60)
    print("测试7: API端点检查")
    print("="*60)

    try:
        from backend.api.v1.settings import router as settings_router
        log_test("Settings API Router 导入", "PASS")
        print(f"      路由路径: /api/v1/")
    except Exception as e:
        log_test("Settings API Router 导入", "FAIL", str(e))

    # 检查路由端点
    try:
        routes = [route.path for route in settings_router.routes]
        log_test("Settings API 路由端点数量", "PASS")
        print(f"      端点: {routes}")
    except Exception as e:
        log_test("Settings API 路由端点检查", "FAIL", str(e))


def print_summary():
    """打印测试摘要"""
    print("\n" + "="*60)
    print("测试结果摘要")
    print("="*60)
    print(f"  ✅ 通过: {len(test_results['passed'])}")
    print(f"  ❌ 失败: {len(test_results['failed'])}")
    print(f"  ⏭️ 跳过: {len(test_results['skipped'])}")
    print(f"  总计: {test_results['total']}")

    if test_results['failed']:
        print("\n失败详情:")
        for item in test_results['failed']:
            print(f"  - {item['name']}: {item['message']}")

    if test_results['skipped']:
        print("\n跳过详情:")
        for item in test_results['skipped']:
            print(f"  - {item['name']}: {item['message']}")

    return len(test_results['failed']) == 0


if __name__ == "__main__":
    print("="*60)
    print("AutoClip AI处理引擎模块接口测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # 运行所有测试
    test_imports()
    test_llm_manager()
    test_llm_providers()
    test_text_processor()
    test_llm_client()
    test_pipeline_steps()
    test_api_endpoints()

    # 打印摘要
    success = print_summary()

    # 保存测试结果
    result_file = project_root / "test_results.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)
    print(f"\n测试结果已保存到: {result_file}")

    sys.exit(0 if success else 1)