#!/usr/bin/env python3
"""展示 yolo_analysis 的输出结果"""

import sys
import os
import json

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.tools.yolo_analysis import analyze_yolo_content

def show_yolo_analysis_output():
    """展示 yolo_analysis 的输出结果"""
    print("=" * 80)
    print("yolo_analysis.analyze_yolo_content 输出结果")
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
    
    print("\n" + "=" * 80)
    print("执行 analyze_yolo_content...")
    print("=" * 80)
    
    try:
        result = analyze_yolo_content(yolo_content, confidence_threshold=0.5)
        print("\n✓ 成功执行 analyze_yolo_content")
        
        print("\n" + "=" * 80)
        print("返回数据结构")
        print("=" * 80)
        print(f"\n顶层键: {list(result.keys())}")
        print(f"\nanalysis 对象包含的键: {list(result['analysis'].keys())}")
        
        print("\n" + "=" * 80)
        print("analysis 主要统计信息")
        print("=" * 80)
        
        analysis = result['analysis']
        print(f"\n- total_detections: {analysis['total_detections']}")
        print(f"- valid_detections: {analysis['valid_detections']}")
        print(f"- low_confidence_detections: {analysis['low_confidence_detections']}")
        print(f"- confidence_threshold: {analysis['confidence_threshold']}")
        print(f"- main_products_count: {analysis['main_products_count']}")
        print(f"- competitors_count: {analysis['competitors_count']}")
        print(f"- price_tags_count: {analysis['price_tags_count']}")
        print(f"\n- product_distribution:")
        for product, count in analysis['product_distribution'].items():
            print(f"    {product}: {count}")
        print(f"\n- confidence_stats: {analysis['confidence_stats']}")
        
        if analysis.get('layout_analysis'):
            print(f"\n- layout_analysis:")
            layout = analysis['layout_analysis']
            for key, value in layout.items():
                print(f"    {key}: {value}")
        
        print("\n" + "=" * 80)
        print("完整 JSON 输出")
        print("=" * 80)
        print("\n(为了展示，会截断过长的内容)")
        
        json_str = json.dumps(result, ensure_ascii=False, indent=2)
        
        if len(json_str) > 10000:
            print(f"\n总输出长度: {len(json_str)} 字符")
            print("\n前 10000 个字符:")
            print(json_str[:10000])
            print("\n... [输出已截断]")
        else:
            print("\n完整输出:")
            print(json_str)
        
        # 保存完整输出到文件
        output_file = os.path.join(os.path.dirname(__file__), "yolo_analysis_output.json")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(json_str)
        
        print(f"\n" + "=" * 80)
        print(f"完整输出已保存到: {output_file}")
        print("=" * 80)
        
    except Exception as e:
        print(f"✗ 执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    show_yolo_analysis_output()
