#!/usr/bin/env python3
"""测试修改后的YOLO分析工具"""

import sys
import os
import json

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.tools.yolo_analysis import analyze_yolo_content

def test_modified_yolo():
    """测试修改后的YOLO分析"""
    print("=" * 60)
    print("测试修改后的YOLO分析工具")
    print("=" * 60)
    
    # 读取示例数据
    data_file = os.path.join(os.path.dirname(__file__), "data", "dataset", "yolo_result.txt")
    
    if not os.path.exists(data_file):
        print(f"错误: 找不到测试文件 {data_file}")
        return False
    
    with open(data_file, "r", encoding="utf-8") as f:
        yolo_content = f.read()
    
    print("\n1. 调用 analyze_yolo_content...")
    
    try:
        result = analyze_yolo_content(yolo_content, confidence_threshold=0.5)
        
        print(f"✓ 成功执行 analyze_yolo_content")
        
        # 检查返回的结构
        print("\n2. 检查返回数据结构...")
        
        if not isinstance(result, dict):
            print(f"✗ 返回结果不是字典类型，而是 {type(result)}")
            return False
        
        required_keys = ["analysis", "raw_boxes"]
        for key in required_keys:
            if key not in result:
                print(f"✗ 返回结果缺少键: {key}")
                return False
            print(f"✓ 找到键: {key}")
        
        # 检查 analysis 是否是字典形式
        analysis = result["analysis"]
        print(f"\n3. 检查 analysis 结构...")
        print(f"  - total_detections: {analysis.get('total_detections', 'N/A')}")
        print(f"  - main_products_count: {analysis.get('main_products_count', 'N/A')}")
        print(f"  - competitors_count: {analysis.get('competitors_count', 'N/A')}")
        print(f"  - price_tags_count: {analysis.get('price_tags_count', 'N/A')}")
        
        # 检查是否有旧的键（确保我们移除了它们）
        if "recommendations" in analysis:
            print("✗ analysis 中仍然包含 recommendations 键")
            return False
        print("✓ analysis 中不包含已移除的键（如 recommendations）")
        
        # 测试是否可以序列化为JSON
        print("\n4. 测试 JSON 序列化...")
        try:
            json_str = json.dumps(result, ensure_ascii=False, indent=2)
            print("✓ 成功序列化为JSON")
        except Exception as e:
            print(f"✗ JSON 序列化失败: {e}")
            return False
        
        print("\n" + "=" * 60)
        print("所有测试通过! ✅")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"✗ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_modified_yolo()
    sys.exit(0 if success else 1)
