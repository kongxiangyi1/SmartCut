"""
P0问题修复集成测试

验证以下P0问题的修复方案：
1. 数据依赖问题：步骤间通过step_manifest验证依赖
2. LLM重试机制：统一重试策略和降级机制
3. ID分配混乱：全局ID管理器确保一致性
"""

import logging
import json
import tempfile
from pathlib import Path
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入修复后的模块
try:
    from backend.pipeline.step_manifest import (
        StepManifestManager,
        STEPS_DEPENDENCIES
    )
    from backend.pipeline.global_id_manager import GlobalIDManager, IDMappingValidator
    from backend.pipeline.llm_retry_manager import LLMRetryManager
    logger.info("修复模块导入成功")
except ImportError as e:
    logger.error(f"修复模块导入失败: {e}")
    raise


class TestRunner:
    """测试运行器"""
    
    def __init__(self):
        self.test_results = []
        self.current_test = None
        
    def run_test(self, test_name: str, test_func):
        """运行单个测试"""
        self.current_test = test_name
        logger.info("=" * 60)
        logger.info(f"运行测试: {test_name}")
        logger.info("=" * 60)
        
        try:
            result = test_func()
            self.test_results.append({
                "test_name": test_name,
                "result": "PASSED" if result else "FAILED",
                "timestamp": datetime.now().isoformat()
            })
            logger.info(f"测试 {test_name}: {'PASSED' if result else 'FAILED'}")
            return result
        except Exception as e:
            logger.error(f"测试 {test_name} 异常: {e}")
            self.test_results.append({
                "test_name": test_name,
                "result": "ERROR",
                "error": str(e)
            })
            return False
    
    def print_summary(self):
        """打印测试摘要"""
        logger.info("=" * 60)
        logger.info("测试摘要")
        logger.info("=" * 60)
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["result"] == "PASSED")
        failed = sum(1 for r in self.test_results if r["result"] == "FAILED")
        errors = sum(1 for r in self.test_results if r["result"] == "ERROR")
        
        logger.info(f"total Tests: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Errors: {errors}")
        
        if passed == total:
            logger.info("🎉 所有测试通过！")
            return True
        else:
            logger.warning("❌ 部分测试失败")
            return False


def test_step_manifest():
    """测试步骤数据契约（P0 #1）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        manifest_path = tmp_path / "data"
        manifest_path.mkdir(parents=True)
        
        # 创建步骤1的SRT块目录
        step1_chunks = manifest_path / "step1_srt_chunks"
        step1_chunks.mkdir()
        
        # 创建一个示例SRT块
        chunk_file = step1_chunks / "chunk_0.json"
        with open(chunk_file, 'w', encoding='utf-8') as f:
            json.dump([{"index": 1, "start_time": "00:00:00", "end_time": "00:00:30", "text": "测试"}], f)
        
        # 创建manifest管理器
        manifest = StepManifestManager(project_id="test", metadata_dir=manifest_path)
        
        # 验证步骤2的依赖
        result = manifest.validate_step_dependencies("step2_timeline")
        logger.info(f"步骤依赖验证结果: {result}")
        
        return result


def test_global_id_manager():
    """测试全局ID管理器（P0 #3）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        id_path = tmp_path / "data"
        id_path.mkdir(parents=True)
        
        # 创建ID管理器
        id_manager = GlobalIDManager(project_id="test", metadata_dir=id_path)
        
        # 测试ID生成
        test_cases = [
            ("step1", "chunk_0"),
            ("step2", "outline_1"),
            ("step3", "scoring_2"),
        ]
        
        # 记录第一次生成的ID
        first_ids = {}
        for source, source_id in test_cases:
            first_id = id_manager.get_or_create_id(source, source_id)
            first_ids[source] = first_id
        
        # 验证重复请求返回相同ID
        for source, source_id in test_cases:
            same_id = id_manager.get_or_create_id(source, source_id)
            if same_id != first_ids[source]:
                logger.error(f"ID不一致: {source}:{source_id} -> {first_ids[source]} vs {same_id}")
                return False
        
        logger.info(f"所有ID测试通过: {first_ids}")
        return True


def test_id_mapping_validator():
    """测试ID映射验证器（P0 #3）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        id_path = tmp_path / "data"
        id_path.mkdir(parents=True)
        
        # 创建ID管理器
        id_manager = GlobalIDManager(project_id="test", metadata_dir=id_path)
        validator = IDMappingValidator(id_manager)
        
        # 创建测试数据
        step2_timeline = [
            {"outline": "话题1", "start_time": "00:00:00", "end_time": "00:00:30"},
            {"outline": "话题2", "start_time": "00:00:30", "end_time": "00:01:00"},
        ]
        
        # 生成全局ID
        for item in step2_timeline:
            item["id"] = id_manager.get_or_create_id("step2", item["outline"])
        
        # 验证测试
        result = validator.validate_step2_timeline(step2_timeline)
        
        # 检查是否有重复ID
        ids = [item["id"] for item in step2_timeline]
        if len(ids) != len(set(ids)):
            logger.error("检测到重复ID")
            return False
        
        logger.info(f"ID验证通过: {ids}")
        return result


def test_llm_retry_manager():
    """测试LLM重试管理器（P0 #2）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cache_path = tmp_path / "cache"
        
        # 创建mock LLM调用函数
        call_count = [0]
        
        def mock_llm_call(prompt, input_data, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:  # 前两次失败
                raise Exception("Mock LLM error")
            # 第三次成功
            return {
                "content": "测试结果",
                "model": "qwen-plus"
            }
        
        # 创建重试管理器
        retry_manager = LLMRetryManager(max_retries=3, cache_dir=cache_path)
        
        # 测试调用
        try:
            response = retry_manager.call_with_retry(
                call_func=mock_llm_call,
                prompt="测试提示词",
                input_data={"test": "data"},
                step_name="test_step",
                chunk_index=0,
                cache_enabled=False  # 测试期间禁用缓存
            )
            
            logger.info(f"重试调用成功，返回: {response}")
            logger.info(f"总共尝试次数: {call_count[0]}")
            
            return call_count[0] == 3 and response.get("content") == "测试结果"
            
        except Exception as e:
            logger.error(f"重试调用失败: {e}")
            return False


def test_full_pipeline_integration():
    """测试完整Pipeline集成（P0 #1, #2, #3）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        data_path = tmp_path / "project_data"
        data_path.mkdir(parents=True)
        
        # 1. 创建步骤1的依赖数据
        step1_chunks = data_path / "step1_chunks"
        step1_srt_chunks = data_path / "step1_srt_chunks"
        step1_chunks.mkdir()
        step1_srt_chunks.mkdir()
        
        chunk_file = step1_srt_chunks / "chunk_0.json"
        with open(chunk_file, 'w', encoding='utf-8') as f:
            json.dump([
                {"index": 1, "start_time": "00:00:00", "end_time": "00:00:30", "text": "欢迎来到直播间"},
                {"index": 2, "start_time": "00:00:30", "end_time": "00:01:00", "text": "今天给大家带来好货"},
            ], f)
        
        # 2. 创建manifest管理器
        manifest = StepManifestManager(project_id="integration_test", metadata_dir=data_path)
        manifest.validate_step_dependencies("step2_timeline")  # 应该通过验证
        manifest.mark_step_completed("step1_outline", success=True)
        
        # 3. 创建ID管理器
        id_manager = GlobalIDManager(project_id="integration_test", metadata_dir=data_path)
        
        # 4. 模拟Step2处理
        timeline_data = [
            {"outline": "产品介绍", "start_time": "00:00:00", "end_time": "00:00:30"},
            {"outline": "用户问答", "start_time": "00:00:30", "end_time": "00:01:00"},
        ]
        
        # 生成全局ID
        for item in timeline_data:
            item["id"] = id_manager.get_or_create_id("step2", item["outline"])
        
        # 5. 保存step2结果
        step2_path = data_path / "step2_timeline.json"
        with open(step2_path, 'w', encoding='utf-8') as f:
            json.dump(timeline_data, f, ensure_ascii=False, indent=2)
        
        manifest.mark_step_completed("step2_timeline", success=True)
        
        # 验证步骤3的依赖
        result = manifest.validate_step_dependencies("step3_scoring")
        
        logger.info(f"完整集成测试结果: {result}")
        return result


def main():
    """运行所有测试"""
    runner = TestRunner()
    
    # 运行各个测试
    runner.run_test("Step Manifest Validation", test_step_manifest)
    runner.run_test("Global ID Manager", test_global_id_manager)
    runner.run_test("ID Mapping Validator", test_id_mapping_validator)
    runner.run_test("LLM Retry Manager", test_llm_retry_manager)
    runner.run_test("Full Pipeline Integration", test_full_pipeline_integration)
    
    # 打印摘要
    success = runner.print_summary()
    
    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
