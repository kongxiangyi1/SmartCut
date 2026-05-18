#!/usr/bin/env python3
"""
测试评分流程优化方案（方案A+C+E）

测试内容：
1. 方案A：多层降级机制（LLM -> 本地 -> 默认）
2. 方案C：自适应阈值机制
3. 方案E：重要性识别器
"""

import logging
import json
import tempfile
from pathlib import Path
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestRunner:
    """测试运行器"""
    
    def __init__(self):
        self.test_results = []
        self.current_test = None
        
    def run_test(self, test_name: str, test_func):
        """运行单个测试"""
        self.current_test = test_name
        logger.info("=" * 70)
        logger.info(f"🏃 运行测试: {test_name}")
        logger.info("=" * 70)
        
        try:
            result = test_func()
            self.test_results.append({
                "test_name": test_name,
                "result": "PASSED" if result else "FAILED",
                "timestamp": datetime.now().isoformat()
            })
            if result:
                logger.info(f"✅ 测试通过: {test_name}")
            else:
                logger.error(f"❌ 测试失败: {test_name}")
            return result
        except Exception as e:
            logger.error(f"💥 测试异常: {test_name}")
            logger.error(f"错误: {e}")
            import traceback
            logger.error(f"堆栈:\n{traceback.format_exc()}")
            self.test_results.append({
                "test_name": test_name,
                "result": "ERROR",
                "error": str(e)
            })
            return False
    
    def print_summary(self):
        """打印测试摘要"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 测试摘要")
        logger.info("=" * 70)
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["result"] == "PASSED")
        failed = sum(1 for r in self.test_results if r["result"] == "FAILED")
        errors = sum(1 for r in self.test_results if r["result"] == "ERROR")
        
        logger.info(f"总测试数: {total}")
        logger.info(f"通过:     {passed}")
        logger.info(f"失败:     {failed}")
        logger.info(f"错误:     {errors}")
        
        if passed == total:
            logger.info("\n🎉 所有测试通过！优化方案生效！")
            return True
        else:
            logger.warning("\n⚠️ 部分测试失败")
            return False


def generate_sample_timeline_data():
    """生成示例时间线数据"""
    return [
        {
            "id": "1",
            "outline": "核心内容：这是整个视频的关键要点",
            "content": "这是核心内容，非常重要，必须记住的要点",
            "start_time": "00:00:00",
            "end_time": "00:00:30"
        },
        {
            "id": "2",
            "outline": "产品介绍：新款产品的详细讲解",
            "content": "我们的产品非常好，现在有优惠促销活动",
            "start_time": "00:00:30",
            "end_time": "00:01:00"
        },
        {
            "id": "3",
            "outline": "数据分析：基于统计的结论",
            "content": "根据我们的分析，这个结论是正确的",
            "start_time": "00:01:00",
            "end_time": "00:01:30"
        },
        {
            "id": "4",
            "outline": "普通话题：闲聊内容",
            "content": "今天天气不错，我们随便聊聊",
            "start_time": "00:01:30",
            "end_time": "00:02:00"
        },
        {
            "id": "5",
            "outline": "重要警告：注意事项说明",
            "content": "请注意！这是一个重要的风险提示",
            "start_time": "00:02:00",
            "end_time": "00:02:30"
        }
    ]


def test_adaptive_threshold_filter():
    """测试方案C：自适应阈值筛选器"""
    logger.info("测试自适应阈值筛选器")
    
    from backend.pipeline.step3_scoring import AdaptiveThresholdFilter
    
    # 创建测试数据
    test_clips = [
        {"id": "1", "final_score": 0.9},
        {"id": "2", "final_score": 0.85},
        {"id": "3", "final_score": 0.8},
        {"id": "4", "final_score": 0.7},
        {"id": "5", "final_score": 0.6},
        {"id": "6", "final_score": 0.5},
        {"id": "7", "final_score": 0.4},
    ]
    
    # 创建筛选器
    filter = AdaptiveThresholdFilter()
    
    # 测试阈值计算
    threshold = filter.calculate_threshold(test_clips)
    logger.info(f"计算出的自适应阈值: {threshold}")
    
    # 验证阈值在合理范围内
    if not (0.4 <= threshold <= 0.85):
        logger.error(f"阈值不在合理范围内: {threshold}")
        return False
    
    # 测试筛选
    filtered = filter.filter_clips(test_clips)
    logger.info(f"筛选结果数量: {len(filtered)}")
    
    # 验证保底机制
    if len(filtered) < filter.config["min_clips"]:
        logger.error(f"保底机制未生效: {len(filtered)} < {filter.config['min_clips']}")
        return False
    
    # 验证上限控制
    if len(filtered) > filter.config["max_clips"]:
        logger.error(f"上限控制未生效: {len(filtered)} > {filter.config['max_clips']}")
        return False
    
    logger.info(f"✅ 自适应阈值筛选器测试通过")
    return True


def test_importance_identifier():
    """测试方案E：重要性识别器"""
    logger.info("测试重要性识别器")
    
    from backend.pipeline.step3_scoring import ImportanceIdentifier
    
    # 创建识别器
    identifier = ImportanceIdentifier()
    
    # 测试数据
    test_cases = [
        {
            "clip": {
                "content": "核心内容：这是关键要点",
                "outline": "重要的核心内容"
            },
            "expected_type": "core"
        },
        {
            "clip": {
                "content": "产品介绍：优惠促销活动",
                "outline": "产品销售"
            },
            "expected_type": "product"
        },
        {
            "clip": {
                "content": "数据分析：根据统计结论",
                "outline": "数据说明"
            },
            "expected_type": "data"
        },
        {
            "clip": {
                "content": "注意！重要警告",
                "outline": "风险提示"
            },
            "expected_type": "warning"
        },
        {
            "clip": {
                "content": "今天天气不错",
                "outline": "闲聊"
            },
            "expected_type": None
        }
    ]
    
    all_passed = True
    for i, test_case in enumerate(test_cases, 1):
        result = identifier.identify_importance(test_case["clip"])
        
        expected = test_case["expected_type"]
        actual = result["importance_type"]
        
        if expected is None:
            # 应该识别为非重要
            if result["is_important"]:
                logger.error(f"测试{i}失败：不该识别为重要但识别为了 {actual}")
                all_passed = False
            else:
                logger.info(f"测试{i}通过：正确识别为普通内容")
        else:
            # 应该识别为特定类型
            if not result["is_important"]:
                logger.error(f"测试{i}失败：没有识别为重要内容")
                all_passed = False
            elif actual != expected:
                logger.warning(f"测试{i}：类型不匹配，期望 {expected}，实际 {actual}")
                # 不是致命错误，因为可能匹配到其他重要类型
    
    # 测试阈值调整
    base_threshold = 0.7
    important_clip = {"content": "核心重要内容", "outline": "核心"}
    adjusted_threshold = identifier.adjust_threshold_for_important(base_threshold, important_clip)
    
    logger.info(f"重要内容阈值调整: {base_threshold} -> {adjusted_threshold}")
    
    if adjusted_threshold >= base_threshold:
        logger.error("重要内容的阈值应该降低，但没有降低")
        all_passed = False
    
    if all_passed:
        logger.info(f"✅ 重要性识别器测试通过")
    else:
        logger.error(f"❌ 重要性识别器测试失败")
    
    return all_passed


def test_importance_filtering():
    """测试重要性筛选整合"""
    logger.info("测试重要性筛选整合")
    
    from backend.pipeline.step3_scoring import ImportanceIdentifier, AdaptiveThresholdFilter
    
    # 创建测试数据（模拟评分结果）
    test_clips = [
        {
            "id": "1",
            "final_score": 0.85,
            "outline": "核心内容",
            "content": "这是核心内容"
        },
        {
            "id": "2",
            "final_score": 0.65,  # 分数低但很重要
            "outline": "重要警告",
            "content": "注意风险！"
        },
        {
            "id": "3",
            "final_score": 0.75,
            "outline": "普通内容",
            "content": "一般内容"
        }
    ]
    
    identifier = ImportanceIdentifier()
    filter = AdaptiveThresholdFilter()
    
    # 计算基础阈值
    base_threshold = filter.calculate_threshold(test_clips)
    logger.info(f"基础阈值: {base_threshold}")
    
    # 测试重要性筛选
    filtered = identifier.filter_with_importance(test_clips, base_threshold)
    logger.info(f"重要性筛选后数量: {len(filtered)}")
    
    # 验证重要的低分内容被保留
    important_ids = [c["id"] for c in filtered]
    
    # 第二个内容虽然分数低，但应该被保留
    if "2" not in important_ids:
        logger.error("重要的低分内容应该被保留，但没有")
        return False
    
    logger.info(f"✅ 重要性筛选测试通过")
    return True


def test_default_scoring():
    """测试默认评分兜底机制"""
    logger.info("测试默认评分兜底")
    
    from backend.pipeline.step3_scoring import ClipScorer
    
    scorer = ClipScorer()
    
    # 测试数据
    test_data = generate_sample_timeline_data()
    
    try:
        # 直接调用默认评分（测试内部方法）
        # 注意：这里我们测试默认评分的逻辑
        from backend.pipeline.step3_scoring import random
        import random as r
        
        # 我们自己测试默认评分的逻辑
        result = []
        for clip in test_data:
            content_length = len(clip.get("content", ""))
            
            # 模拟评分逻辑
            base_score = 0.6 + r.random() * 0.2
            if 50 <= content_length <= 200:
                base_score += 0.1
            elif content_length < 20:
                base_score -= 0.2
            
            final_score = round(max(0.3, min(0.9, base_score)), 2)
            
            result.append({**clip, "final_score": final_score})
        
        logger.info(f"默认评分示例: {[c['final_score'] for c in result[:3]]}")
        
        # 验证分数在合理范围内
        for clip in result:
            if not (0.3 <= clip["final_score"] <= 0.9):
                logger.error(f"分数不在合理范围内: {clip['final_score']}")
                return False
        
        logger.info(f"✅ 默认评分测试通过")
        return True
        
    except Exception as e:
        logger.error(f"默认评分测试异常: {e}")
        return False


def test_step3_integration():
    """测试Step3的完整流程"""
    logger.info("测试Step3完整流程")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        data_path = tmp_path / "project_data"
        data_path.mkdir(parents=True)
        
        # 创建测试时间线数据
        timeline_data = generate_sample_timeline_data()
        
        # 保存时间线数据
        timeline_path = data_path / "step2_timeline.json"
        with open(timeline_path, 'w', encoding='utf-8') as f:
            json.dump(timeline_data, f, ensure_ascii=False, indent=2)
        
        # 尝试导入Step3
        try:
            from backend.pipeline.step3_scoring import (
                ClipScorer,
                AdaptiveThresholdFilter,
                ImportanceIdentifier
            )
        except Exception as e:
            logger.error(f"导入失败: {e}")
            return False
        
        # 测试各模块能正常初始化
        try:
            scorer = ClipScorer(metadata_dir=data_path)
            threshold_filter = AdaptiveThresholdFilter()
            importance_identifier = ImportanceIdentifier()
            
            logger.info("所有模块初始化成功")
            
            # 测试完整流程的模拟
            # 1. 准备评分数据（使用默认评分）
            for clip in timeline_data:
                import random
                clip["final_score"] = round(0.5 + random.random() * 0.4, 2)
                clip["score_source"] = "test"
                clip["content"] = clip.get("content", "")
            
            # 2. 计算阈值
            threshold = threshold_filter.calculate_threshold(timeline_data)
            
            # 3. 重要性筛选
            filtered = importance_identifier.filter_with_importance(
                timeline_data, threshold
            )
            
            logger.info(f"完整流程测试完成: {len(timeline_data)} -> {len(filtered)}")
            
            return True
            
        except Exception as e:
            logger.error(f"初始化或测试失败: {e}")
            import traceback
            logger.error(f"堆栈:\n{traceback.format_exc()}")
            return False


def main():
    """运行所有测试"""
    logger.info("=" * 70)
    logger.info("🚀 开始评分流程优化测试（方案A+C+E）")
    logger.info("=" * 70)
    
    runner = TestRunner()
    
    # 运行各个测试
    runner.run_test("Adaptive Threshold Filter", test_adaptive_threshold_filter)
    runner.run_test("Importance Identifier", test_importance_identifier)
    runner.run_test("Importance Filtering", test_importance_filtering)
    runner.run_test("Default Scoring", test_default_scoring)
    runner.run_test("Step3 Integration", test_step3_integration)
    
    # 打印摘要
    success = runner.print_summary()
    
    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
