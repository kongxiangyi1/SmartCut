# AutoClip 流水线优化回滚方案

## 🚨 快速回滚

如果优化后出现问题，可通过以下任一方式快速回滚：

### 方式 1：API 回滚（推荐）

```bash
# 切换回原流水线
curl -X POST http://localhost:8090/api/v1/pipeline/switch \
  -H "Content-Type: application/json" \
  -d '{"mode": "legacy"}'

# 验证切换
curl http://localhost:8090/api/v1/pipeline/status
```

### 方式 2：环境变量回滚

```bash
# 设置环境变量
export PIPELINE_MODE=legacy

# 重启服务
./restart.sh
```

### 方式 3：配置文件回滚

编辑 `backend/pipeline/optimized/config.py`：

```python
OPTIMIZED_PIPELINE_ENABLED = False  # 改为 False
```

---

## 📋 回滚检查清单

### 1. 确认回滚成功

- [ ] API 返回 `mode: "legacy"`
- [ ] `/api/v1/pipeline/status` 显示 `optimization_enabled: false`
- [ ] 新项目使用原流水线处理
- [ ] 现有项目不受影响

### 2. 验证功能正常

- [ ] 项目可以正常创建
- [ ] 视频可以正常处理
- [ ] 切片生成正常
- [ ] 合集生成正常
- [ ] WebSocket 进度更新正常

### 3. 收集回滚原因

请记录以下信息以便后续分析：

```markdown
## 回滚报告

**日期**: YYYY-MM-DD
**时间**: HH:MM
**回滚原因**: 
- [ ] 性能下降
- [ ] 输出质量下降
- [ ] 功能异常
- [ ] 其他: __

**具体问题描述**: 
...

**影响的项目数**: N

**持续时间**: X 分钟
```

---

## 🔧 故障排查

### 问题 1：优化流水线处理失败

**症状**：使用优化流水线时任务失败

**排查步骤**：
1. 检查日志：`tail -f logs/backend.log | grep "optimized"`
2. 验证 SRT 文件是否正常
3. 检查 LLM API 是否可用
4. 运行验证脚本：`python scripts/validate_optimized_pipeline.py`

**解决方案**：
```bash
# 临时回滚到原流水线
curl -X POST http://localhost:8090/api/v1/pipeline/switch \
  -H "Content-Type: application/json" \
  -d '{"mode": "legacy"}'
```

### 问题 2：输出质量下降

**症状**：优化流水线生成的切片质量不如原流水线

**排查步骤**：
1. 对比相同视频的两种输出
2. 检查 `clips_metadata.json` 中的评分
3. 验证时间区间是否正确

**解决方案**：
```bash
# 切换到 A/B 测试模式
curl -X POST http://localhost:8090/api/v1/pipeline/switch \
  -H "Content-Type: application/json" \
  -d '{"mode": "ab_test", "ab_test_ratio": 0.1}'
```

### 问题 3：API 路由不可用

**症状**：`/api/v1/pipeline/switch` 返回 404

**排查步骤**：
1. 检查 `backend/api/v1/__init__.py` 是否包含 `pipeline_switch`
2. 检查服务器是否重启
3. 检查导入错误

**解决方案**：
```bash
# 重启后端服务
pkill -f "uvicorn.*backend.main"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8090
```

---

## 📊 监控指标

回滚后请持续监控以下指标（至少 24 小时）：

### 性能指标
- [ ] API 响应时间
- [ ] LLM API 调用次数
- [ ] 处理任务成功率

### 质量指标
- [ ] 切片数量变化
- [ ] 合集数量变化
- [ ] 用户反馈

### 系统指标
- [ ] CPU 使用率
- [ ] 内存使用率
- [ ] 错误日志数量

---

## 📞 获取支持

如果回滚后问题持续，请联系：

- **GitHub Issues**: https://github.com/zhouxiaoka/autoclip/issues
- **邮箱**: christine_zhouye@163.com

回滚报告模板已保存在 `logs/rollback_report.md`
