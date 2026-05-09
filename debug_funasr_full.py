import sys
from pathlib import Path
sys.path.insert(0, 'e:/ClipProject/autoclip-main1/autoclip-main')

from funasr import AutoModel

audio_path = 'e:/ClipProject/autoclip-main1/autoclip-main/data/projects/a9e1527c-13a2-496d-a06a-5a80b3c5648e/metadata/input_audio.wav'

print("加载FunASR模型...")
model = AutoModel(
    model="paraformer-zh",
    vad_model="fsmn-vad",
    punc_model="ct-punc",
    device="cpu"
)

print("开始FunASR转录...")
result = model.generate(input=audio_path, return_timestamp=True)

print(f"\n结果类型: {type(result)}")
print(f"结果长度: {len(result)}")

if result:
    segment = result[0]
    print(f"\n第一个元素类型: {type(segment)}")
    if isinstance(segment, dict):
        print(f"键: {list(segment.keys())}")
        text = segment.get('text', segment.get('value', ''))
        timestamps = segment.get('timestamp', segment.get('time_stamp', []))

        print(f"\ntext长度: {len(text)} 字符")
        print(f"text前200字符: {text[:200]}")
        print(f"text后200字符: {text[-200:]}")

        print(f"\ntimestamps类型: {type(timestamps)}")
        if isinstance(timestamps, list):
            print(f"timestamps长度: {len(timestamps)}")
            if len(timestamps) > 0:
                print(f"第一个时间戳: {timestamps[0]}")
                print(f"最后一个时间戳: {timestamps[-1]}")

                # 计算总时长
                if isinstance(timestamps[0], list) and len(timestamps[0]) >= 2:
                    first_start = timestamps[0][0] / 1000.0
                    last_end = timestamps[-1][1] / 1000.0
                    print(f"\n覆盖时间范围: {first_start:.1f}秒 到 {last_end:.1f}秒")
                    print(f"覆盖总时长: {last_end - first_start:.1f}秒 = {(last_end - first_start) / 60:.1f}分钟")
