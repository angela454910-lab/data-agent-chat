#!/usr/bin/env python3
"""展示 yolo_analysis 和 dataset_tools 的输出结果"""

import sys
import os
import json

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.tools.yolo_analysis import analyze_yolo_content
from app.tools.dataset_tools import analyze_yolo_results

def show_outputs():
    """展示两个工具的输出结果"""
    print("=" * 80)
    print("展示 yolo_analysis 和 dataset_tools 的输出结果")
    print("=" * 80)
    
    # 读取示例数据
    data_file = os.path.join(os.path.dirname(__file__), "data", "dataset", "yolo_result.txt")
    
    if not os.path.exists(data_file):
        print(f"错误: 找不到测试文件 {data_file}")
        return
    
    with open(data_file, "r", encoding="utf-8") as f:
        yolo_content = f.read()
    
    print(f"\n使用的 yolo 数据文件: {data_file}")
    print(f"文件大小: {os.path.getsize(data_file)} 字节")
    
    # 1. 测试 yolo_analysis 的 analyze_yolo_content
    print("\n" + "=" * 80)
    print("1. yolo_analysis.analyze_yolo_content 输出")
    print("=" * 80)
    
    try:
        result1 = analyze_yolo_content(yolo_content, confidence_threshold=0.5)
        print("\n✓ 成功执行 analyze_yolo_content")
        print("\n返回数据结构:")
        print(f"  - 顶层键: {list(result1.keys())}")
        print(f"  - analysis 键: {list(result1['analysis'].keys())}")
        
        # 显示 analysis 的主要内容
        print("\nanalysis 主要内容:")
        analysis = result1['analysis']
        for key in ['total_detections', 'valid_detections', 'low_confidence_detections', 
                   'confidence_threshold', 'main_products_count', 'competitors_count', 
                   'price_tags_count', 'product_distribution', 'confidence_stats']:
            if key in analysis:
                print(f"  - {key}: {analysis[key]}")
        
        # 显示 JSON 格式的输出（截断）
        print("\n完整 JSON 输出（截断）:")
        json_str = json.dumps(result1, ensure_ascii=False, indent=2)
        if len(json_str) > 3000:
            print(json_str[:3000] + "\n... [输出已截断，总长度: {} 字符]".format(len(json_str)))
        else:
            print(json_str)
        
    except Exception as e:
        print(f"✗ 执行失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 2. 测试 dataset_tools 的 analyze_yolo_results
    print("\n" + "=" * 80)
    print("2. dataset_tools.analyze_yolo_results 输出")
    print("=" * 80)
    
    try:
        # 因为 analyze_yolo_results 是一个 LangChain tool，我们需要直接调用它
        result2 = analyze_yolo_results._run(yolo_content=yolo_content, confidence_threshold=0.5)
        
        print("\n✓ 成功执行 analyze_yolo_results")
        
        # 尝试解析 JSON
        try:
            parsed = json.loads(result2)
            print("\n返回的 JSON 数据结构:")
            if isinstance(parsed, dict):
                print(f"  - 顶层键: {list(parsed.keys())}")
                if 'analysis' in parsed:
                    print(f"  - analysis 键: {list(parsed['analysis'].keys())}")
            
            print("\n完整输出:")
            if len(result2) > 5000:
                print(result2[:5000] + "\n... [输出已截断，总长度: {} 字符]".format(len(result2)))
            else:
                print(result2)
        except json.JSONDecodeError:
            print("\n返回的不是 JSON，直接输出内容:")
            if len(result2) > 5000:
                print(result2[:5000] + "\n... [输出已截断]")
            else:
                print(result2)
                
    except Exception as e:
        print(f"✗ 执行失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("完成！")
    print("=" * 80)

if __name__ == "__main__":
    show_outputs()
