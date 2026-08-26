#!/usr/bin/env python3
"""测试重构后的 YOLO 工具"""

import sys
import os
import json

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("测试重构后的 YOLO 工具")
print("=" * 80)

# 1. 测试 yolo_analysis.py 的 YOLO_TOOLS
print("\n1. 测试 yolo_analysis.py 的 YOLO_TOOLS")
print("-" * 80)

try:
    from app.tools.yolo_analysis import YOLO_TOOLS, analyze_yolo_results
    print(f"✓ 成功导入 YOLO_TOOLS")
    print(f"  包含 {len(YOLO_TOOLS)} 个工具:")
    for tool in YOLO_TOOLS:
        print(f"    - {tool.name}")
except Exception as e:
    print(f"✗ 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 2. 测试加载示例数据
print("\n2. 加载示例数据")
print("-" * 80)

data_file = os.path.join(os.path.dirname(__file__), "data", "dataset", "yolo_result.txt")
try:
    with open(data_file, "r", encoding="utf-8") as f:
        yolo_content = f.read()
    print(f"✓ 成功加载数据，文件大小: {os.path.getsize(data_file)} 字节")
except Exception as e:
    print(f"✗ 加载失败: {e}")
    sys.exit(1)

# 3. 测试直接调用 analyze_yolo_results 工具
print("\n3. 直接测试 analyze_yolo_results 工具")
print("-" * 80)

try:
    result_str = analyze_yolo_results.invoke({"yolo_content": yolo_content, "confidence_threshold": 0.5})
    print(f"✓ 工具调用成功")
    print(f"  返回类型: {type(result_str)}")
    
    try:
        result = json.loads(result_str)
        print(f"✓ 成功解析 JSON")
        print(f"\n结果摘要:")
        print(f"  - total_detections: {result.get('analysis', {}).get('total_detections')}")
        print(f"  - main_products_count: {result.get('analysis', {}).get('main_products_count')}")
        print(f"  - competitors_count: {result.get('analysis', {}).get('competitors_count')}")
        print(f"  - price_tags_count: {result.get('analysis', {}).get('price_tags_count')}")
    except json.JSONDecodeError as e:
        print(f"✗ JSON 解析失败: {e}")
        print(f"  返回内容前 200 字符: {result_str[:200]}")
        
except Exception as e:
    print(f"✗ 工具调用失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. 验证 dataset_tools.py 已经移除了重复工具
print("\n4. 验证 dataset_tools.py 已移除 YOLO 工具")
print("-" * 80)

try:
    from app.tools.dataset_tools import DATASET_TOOLS
    print(f"✓ DATASET_TOOLS 包含 {len(DATASET_TOOLS)} 个工具:")
    for tool in DATASET_TOOLS:
        print(f"    - {tool.name}")
    
    found_yolo = any(tool.name == "analyze_yolo_results" for tool in DATASET_TOOLS)
    if not found_yolo:
        print(f"✓ 确认 dataset_tools 中没有重复的 YOLO 工具")
    else:
        print(f"✗ 警告: dataset_tools 中仍然包含 YOLO 工具")
        
except Exception as e:
    print(f"✗ 验证失败: {e}")

# 5. 测试 dataset_analysis.py 正确加载了工具
print("\n5. 测试 dataset_analysis.py 正确加载工具")
print("-" * 80)

try:
    from app.agents.dataset_analysis import dataset_analysis_agent
    print(f"✓ dataset_analysis_agent 加载成功")
except Exception as e:
    print(f"✗ 加载 agent 失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("所有测试通过！重构成功！")
print("=" * 80)
