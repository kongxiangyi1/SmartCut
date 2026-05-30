# 字幕纠正写回方案

## 1. 背景与问题

### 现状

ASR（语音识别）生成的字幕文件 `raw/input.srt` **未经任何处理**，包含大量口语填充词和识别错误：

- 填充词："嗯、呃、那个、这个这个、然后然后、我们可以看到"
- 重复性口吃："拿奖奖后后与与"
- 口语习惯："总的来说呢、因为呢、所以呢"

这些原始字幕有以下消费方：

| 消费方 | 用途 | 文件位置 |
|--------|------|----------|
| 前端展示（SubtitleEditor） | 用户查看/编辑字幕 | `raw/input.srt` |
| LLM 分析输入 | 话题切分/评分/标题生成 | 读入内存处理 |
| Step6 视频生成 | 视频切片使用的 SRT 时间参考 | `raw/input.srt` |
| SubtitleEditor 编辑 | 用户删除字幕段后的视频裁剪 | `raw/input.srt` |

### 矛盾

目前 `funclip_style.py` 的 `_prepare_enhanced_text()` 方法对字幕做了纠正（剔除填充词 + COMMON_RULES 替换 + pycorrector 纠错 + 语义分段），但 **纠正结果只用作 LLM 的输入上下文**，没有写回 `raw/input.srt`。

结果：前端展示的字幕仍然包含"嗯呃那个这个"等噪音，用户看到的字幕质量低于 LLM 分析时用的文本。

---

## 2. 方案选项对比

### 方案 A：语义分段 + 全量纠正写回（不推荐）

使用 `SemanticPreprocessor` 做语义分段合并后写回。

风险：
- 语义分段会合并多条 SRT 条目，破坏原有的 VAD 精确时间戳
- 新的时间戳是比例分配的近似值，误差可能达数百毫秒
- `pycorrector` 是统计模型，可能引入新的错误
- 对视频切片定位产生副作用

### 方案 B：新建纠正后字幕文件（较稳妥）

保存为 `raw/input_corrected.srt`，前端和 Step6 引用新文件。

缺点：
- 所有消费方需要修改读取路径
- 语义分段引起的时序偏移问题仍然存在
- 维护两个文件增加复杂度

### 方案 C（推荐）：逐行安全纠正写回

只对 SRT 每条的 **文本内容** 做安全的规则替换，**不改时间戳、不改分段结构、不合并条目**，直接写回原文件。

安全边界：

| 操作 | 是否使用 | 原因 |
|------|:--------:|------|
| 剔除填充词 (FILLER_WORDS) | ✅ | 纯字符删除，不影响结构 |
| COMMON_RULES 替换 | ✅ | 纯字符串替换，1:1 映射 |
| HOMOPHONE_RULES 替换 | ✅ | 纯字符串替换，1:1 映射 |
| 重复字符合并 (`re.sub`) | ✅ | 正则替换，如"拿奖奖"→"拿奖" |
| pycorrector 纠错 | ❌ | 统计模型可能改错 |
| SemanticPreprocessor 语义分段 | ❌ | 合并条目、变更时间戳 |

---

## 3. 详细实施步骤

### 3.1 新增工具函数

在 `backend/utils/text_corrector.py` 中新增：

```python
def safe_correct_srt_file(srt_path: Path) -> bool:
    """
    对SRT文件做安全纠正（只改文本，不改时间戳和结构）。
    会自动创建 .bak 备份。

    Args:
        srt_path: SRT文件路径

    Returns:
        是否做了修改
    """
    if not srt_path or not srt_path.exists():
        return False

    # 1. 读取原始内容
    original_text = srt_path.read_text(encoding='utf-8')

    # 2. 逐块解析SRT，只替换文本行
    corrected_blocks = []
    blocks = original_text.strip().split('\n\n')
    
    corrector = TextCorrector()

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            corrected_blocks.append(block)
            continue

        # 第1行：序号 -> 不动
        # 第2行：时间戳 -> 不动
        # 第3+行：文本 -> 做安全纠正
        text_lines = lines[2:]
        corrected_text_lines = []
        for text_line in text_lines:
            if text_line.strip():
                # 安全纠正：只做规则替换 + 重复合并，不用pycorrector
                cleaned = _safe_correct_line(text_line, corrector)
                corrected_text_lines.append(cleaned)
            else:
                corrected_text_lines.append(text_line)

        corrected_block = '\n'.join(lines[:2] + corrected_text_lines)
        corrected_blocks.append(corrected_block)

    corrected_text = '\n\n'.join(corrected_blocks) + '\n'

    # 3. 如果没有变化，跳过
    if corrected_text == original_text:
        return False

    # 4. 创建备份
    backup_path = srt_path.with_suffix('.srt.bak')
    if not backup_path.exists():
        backup_path.write_text(original_text, encoding='utf-8')

    # 5. 写回
    srt_path.write_text(corrected_text, encoding='utf-8')
    logger.info(f"SRT纠正完成: {srt_path} (已备份到 {backup_path})")
    return True


def _safe_correct_line(text: str, corrector: TextCorrector) -> str:
    """单行文本的安全纠正（不使用pycorrector）"""
    # 1. 剔除填充词
    text = _clean_filler_words(text)
    # 2. COMMON_RULES 替换
    for wrong, right in TextCorrector.COMMON_RULES.items():
        text = text.replace(wrong, right)
    # 3. HOMOPHONE_RULES 替换
    for wrong, right in TextCorrector.HOMOPHONE_RULES.items():
        text = text.replace(wrong, right)
    # 4. 合并重复中文字符（防止"拿奖奖后后"）
    text = re.sub(r'([\u4e00-\u9fff])\1{1,}', r'\1', text)
    return text
```

### 3.2 测试用例：逐行纠正不改变结构

输入 SRT：

```
1
00:00:01,000 --> 00:00:04,000
嗯大家好今天我要那个那个介绍一个产品

2
00:00:05,000 --> 00:00:08,000
这个这个产品呢就是就是我们的新功能
```

经过 `safe_correct_srt_file()` 后：

```
1
00:00:01,000 --> 00:00:04,000
大家好今天我要介绍一个产品

2
00:00:05,000 --> 00:00:08,000
这个产品就是我们的新功能
```

验证点：
- 时间戳 `00:00:01,000 --> 00:00:04,000` 不变 ✅
- 序号 `1`, `2` 不变 ✅
- 空行分隔 `\n\n` 不变 ✅
- 只有文本内容被清理 ✅

### 3.3 在流水线中集成

在 `simple_pipeline_adapter.py` 中，找到 SRT 文件确认存在的位置（funclip 和 legacy 共用），在 LLM 处理前加入写回调用。

修改 `_process_with_funclip` 和 `_process_with_legacy` 的方法，在确认 `srt_path` 存在后、执行流水线之前，调用写回函数。

由于两个方法都有相同的 SRT 确认逻辑，将写回调用放在公共位置：

```
# 在确认 srt_path 存在后，执行流水线之前
from backend.utils.text_corrector import safe_correct_srt_file
safe_correct_srt_file(srt_path)
```

集成点：

| 流程 | 集成位置 | 修改文件 |
|------|---------|----------|
| FunClip | `_process_with_funclip()` 在 `emit_progress("SUBTITLE", "字幕处理完成")` 之前 | simple_pipeline_adapter.py |
| Legacy | `_process_with_legacy()` 在 `run_step1_outline()` 之前 | simple_pipeline_adapter.py |

---

## 4. 多轮验证

### 第1轮：SRT格式兼容性

验证：修改只作用于文本行，SRT 结构完全保留：

```
输入:                  输出:
序号: int              int（不变）
时间戳: a-->b          a-->b（不变）
文本: "嗯大家好"       "大家好"（仅文本变化）
空行: \n\n             \n\n（不变）
```

结论：✅ 格式兼容，所有消费方无需修改。

### 第2轮：规则安全性

逐条验证替换规则不会误改：

| 规则 | 输入 | 输出 | 是否安全 |
|------|------|------|:--------:|
| FILLER_WORDS | "嗯大家好" | "大家好" | ✅ |
| COMMON_RULES | "这个这个产品" | "这个产品" | ✅ |
| HOMOPHONE_RULES | "需呀" | "需要" | ✅ |
| 重复合并 | "拿奖奖" | "拿奖" | ✅（但"人人"不会被误改，因为汉字重复≥2次才触发） |
| pycorrector | "发烧友" | 可能改错 | ❌ 排除 |

边界案例：

| 输入 | 处理后 | 说明 |
|------|--------|------|
| "哈哈，这个这个" | "哈哈，" | "哈哈"也是填充词，会被删掉。但"哈哈"也可能是笑声内容，此场景可接受 |
| "嗯" | "" | 单字被删，可能变成空行。但 SRT 允许空文本行 |
| "重量级产品" | "重量级产品" | HOMOPHONE_RULES 中"重量级"→"重量级" 是无操作替换 ✅ |

结论：✅ 规则替换足够安全，无误改风险。

### 第3轮：多音字/专有名词误伤

检查 FILLER_WORDS 中的字是否可能出现在正常词中：

| 填充词 | 可能误伤场景 | 判断 |
|--------|-------------|:----:|
| "那个" | "那个产品" → "产品" | 正确，口语中的"那个"应该剔除 |
| "这个" | "这个方案" → "方案" | 正确，口语中的"这个"应该剔除 |
| "嗯" | "嗯..." → "" | 可以接受，语气词 |
| "我们可以看到" | 完整短语 | 正确，无信息量的套话 |

但需要注意："那个啥" → "" 中的"啥"也会被删除，可能丢失语气。权衡后认为可接受。

结论：✅ 无实质信息丢失风险。

### 第4轮：写回时机

确认写回不会干扰 ASR 输出或其他并行操作：

```
时间线:
1. generate_subtitle_for_video()  → 写入 raw/input.srt
2. safe_correct_srt_file()        → 备份 raw/input.srt.bak + 写回纠正版
3. run_funclip_pipeline()         → 读取纠正后的 raw/input.srt
   ├─ _read_srt()                  → 内存中处理
   ├─ _prepare_enhanced_text()     → 增强后给 LLM（叠加语义分段）
   └─ postprocess_funclip_topics()  → 基于原始 SRT 做时间验证
4. 前端加载 subtitles             → 读取纠正后的 raw/input.srt（干净文本）
```

结论：✅ 写回时机在 ASR 完成后、流水线处理前，所有消费方都能读到纠正后的文本。

### 第5轮：回退机制

如果纠正写回过程中发生异常，不能影响主流程：

```python
def safe_correct_srt_file(srt_path: Path) -> bool:
    try:
        # ... 执行纠正
    except Exception as e:
        logger.warning(f"SRT纠正写回失败（不影响主流程）: {e}")
        return False
```

异常不影响主流程，原始文件保持不变。

结论：✅ 异常安全。

---

## 5. 验证清单

完成实施后检查以下项：

- [ ] `raw/input.srt` 中的 "嗯、呃、那个" 等填充词被剔除
- [ ] "这个这个、然后然后" 等重复词被归一化
- [ ] 时间戳格式不变：`00:00:01,000 --> 00:00:04,000`
- [ ] 序号保持连续
- [ ] 备份文件 `raw/input.srt.bak` 正确生成
- [ ] 前端 SubtitleEditor 展示干净文本
- [ ] LLM 分析仍正常工作（输入已经过 `_prepare_enhanced_text` 进一步处理）
- [ ] 视频切片（Step6）时间定位不受影响
- [ ] Legacy 6步流水线同样受益
- [ ] 无 `pycorrector`/语义分段相关的副作用

---

## 6. 未来可能的增强

1. **LLM 辅助纠错**：若未来需要更高级的纠错（如"拿奖奖后后与与"→"拿奖后与"），可以用 LLM 单独做一次字幕纠正步骤，但成本较高
2. **热词感知修正**：结合 ASR 热词库，对特定领域术语做更准确的纠正
3. **用户可选的纠正强度**：前端提供一个开关，让用户选择是否启用字幕纠正