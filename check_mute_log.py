import codecs

try:
    with codecs.open(r'E:\ClipProject\autoclip-main1\autoclip-main\backend.log', 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # 搜索静音相关
    mute_lines = []
    error_lines = []
    step6_lines = []

    for i, line in enumerate(lines[-500:], start=len(lines)-500):
        if '静音' in line or 'mute' in line.lower():
            mute_lines.append((i+1, line.strip()))
        if 'ERROR' in line or '失败' in line or 'error' in line.lower():
            error_lines.append((i+1, line.strip()))
        if 'step6' in line.lower() or 'Step 6' in line or '视频切割' in line or 'run_step6' in line.lower():
            step6_lines.append((i+1, line.strip()))

    print("=== 静音相关日志 ===")
    for num, line in mute_lines[-20:]:
        print(f"{num}: {line[:200]}")

    print("\n=== Step6相关日志 ===")
    for num, line in step6_lines[-20:]:
        print(f"{num}: {line[:200]}")

    print("\n=== 最新错误日志 ===")
    for num, line in error_lines[-30:]:
        print(f"{num}: {line[:200]}")

except Exception as e:
    print(f"Error: {e}")
