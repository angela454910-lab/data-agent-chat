#!/usr/bin/env python3
"""Analyze YOLO detection results file."""

import json
import re
from collections import defaultdict
from typing import Dict, List, Any


def parse_yolo_result(file_path: str) -> Dict[str, Any]:
    """Parse YOLO result file and extract detection boxes."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract the boxes array using regex
    boxes_match = re.search(r'boxes:\s*\[(.*?)\],\s*accelerator', content, re.DOTALL)
    if not boxes_match:
        raise ValueError("Could not find boxes array in file")
    
    boxes_str = boxes_match.group(1)
    
    # Parse each box manually with better handling
    boxes = []
    
    # Split into individual box strings
    # We need to be careful with nested structures, but in this case boxes are flat
    box_strings = []
    current_box = []
    brace_count = 0
    
    for char in boxes_str:
        if char == '{':
            if brace_count == 0:
                current_box = []
            brace_count += 1
            current_box.append(char)
        elif char == '}':
            brace_count -= 1
            current_box.append(char)
            if brace_count == 0:
                box_strings.append(''.join(current_box))
        elif brace_count > 0:
            current_box.append(char)
    
    for box_str in box_strings:
        try:
            # Parse the box manually
            box = {}
            
            # Extract key-value pairs
            # Pattern: key: value, where value can be a number, or unquoted string
            pairs = re.findall(r'(\w+):\s*([^,}]+)', box_str)
            
            for key, value in pairs:
                value = value.strip()
                # Try to parse as number first
                try:
                    if '.' in value or 'e' in value.lower():
                        box[key] = float(value)
                    else:
                        box[key] = int(value)
                except ValueError:
                    # It's a string
                    box[key] = value
            
            if box:
                boxes.append(box)
            
        except Exception as e:
            print(f"Error parsing box: {e}")
            print(f"Box string: {box_str}")
            continue
    
    return {
        "total_boxes": len(boxes),
        "boxes": boxes
    }


def analyze_detections(data: Dict[str, Any], confidence_threshold: float = 0.5) -> Dict[str, Any]:
    """Analyze detections with confidence threshold filtering."""
    boxes = data["boxes"]
    
    # Filter by confidence threshold
    valid_boxes = [box for box in boxes if box.get("confidence", 0) >= confidence_threshold]
    low_conf_boxes = [box for box in boxes if box.get("confidence", 0) < confidence_threshold]
    
    # Categorize
    products = []
    price_tags = []
    competitors = []
    
    # Define main products (百威相关)
    main_product_keywords = ["百威", "BUDWEISER"]
    # Define competitors (哈尔滨等)
    competitor_keywords = ["哈尔滨", "HARBIN"]
    
    for box in valid_boxes:
        class_name = box.get("className", "")
        
        if class_name == "价签":
            price_tags.append(box)
        elif any(keyword in class_name for keyword in main_product_keywords):
            products.append(box)
        elif any(keyword in class_name for keyword in competitor_keywords):
            competitors.append(box)
        else:
            # Other items
            products.append(box)
    
    # Calculate statistics
    stats = {
        "total_detections": len(boxes),
        "valid_detections": len(valid_boxes),
        "low_confidence_detections": len(low_conf_boxes),
        "confidence_threshold": confidence_threshold,
        "main_products_count": len(products),
        "competitors_count": len(competitors),
        "price_tags_count": len(price_tags),
        "product_distribution": defaultdict(int),
        "confidence_stats": {
            "min": min(box.get("confidence", 0) for box in boxes) if boxes else 0,
            "max": max(box.get("confidence", 0) for box in boxes) if boxes else 0,
            "mean": sum(box.get("confidence", 0) for box in boxes) / len(boxes) if boxes else 0,
        }
    }
    
    # Product distribution
    for box in valid_boxes:
        class_name = box.get("className", "Unknown")
        stats["product_distribution"][class_name] += 1
    
    return {
        "statistics": stats,
        "valid_boxes": valid_boxes,
        "low_confidence_boxes": low_conf_boxes,
        "main_products": products,
        "competitors": competitors,
        "price_tags": price_tags,
    }


def generate_analysis_report(analysis: Dict[str, Any]) -> str:
    """Generate a human-readable analysis report."""
    stats = analysis["statistics"]
    
    report = []
    report.append("=" * 60)
    report.append("YOLO 检测结果分析报告")
    report.append("=" * 60)
    report.append("")
    
    report.append("1. 基本统计")
    report.append("-" * 40)
    report.append(f"总检测数量: {stats['total_detections']}")
    report.append(f"有效检测数量 (置信度 ≥ {stats['confidence_threshold']}): {stats['valid_detections']}")
    report.append(f"低置信度检测数量: {stats['low_confidence_detections']}")
    report.append("")
    
    report.append("2. 置信度统计")
    report.append("-" * 40)
    report.append(f"最低置信度: {stats['confidence_stats']['min']:.4f}")
    report.append(f"最高置信度: {stats['confidence_stats']['max']:.4f}")
    report.append(f"平均置信度: {stats['confidence_stats']['mean']:.4f}")
    report.append("")
    
    report.append("3. 产品分类统计")
    report.append("-" * 40)
    report.append(f"主要产品数量: {stats['main_products_count']}")
    report.append(f"竞品数量: {stats['competitors_count']}")
    report.append(f"价签数量: {stats['price_tags_count']}")
    report.append("")
    
    report.append("4. 产品分布详情")
    report.append("-" * 40)
    for product, count in sorted(stats["product_distribution"].items(), key=lambda x: x[1], reverse=True):
        report.append(f"  {product}: {count} 个")
    report.append("")
    
    report.append("5. 主要产品详情 (高置信度)")
    report.append("-" * 40)
    for i, product in enumerate(analysis["main_products"][:10], 1):  # Show first 10
        report.append(f"  {i}. {product['className']}")
        report.append(f"     置信度: {product['confidence']:.4f}")
        report.append(f"     位置: ({product['x1']:.1f}, {product['y1']:.1f}) -> ({product['x2']:.1f}, {product['y2']:.1f})")
    if len(analysis["main_products"]) > 10:
        report.append(f"  ... 还有 {len(analysis['main_products']) - 10} 个产品")
    report.append("")
    
    report.append("6. 销售建议")
    report.append("-" * 40)
    
    # Generate recommendations based on analysis
    if stats['competitors_count'] > 0:
        report.append("  ⚠️ 检测到竞品存在，建议关注竞品陈列位置和价格策略")
    
    if stats['price_tags_count'] == 0:
        report.append("  ⚠️ 未检测到价签，建议补充价格信息以便分析")
    else:
        report.append("  ✓ 检测到价签，可进一步分析价格信息")
    
    if stats['main_products_count'] > stats['competitors_count']:
        report.append("  ✓ 主要产品占据优势，可继续强化陈列")
    else:
        report.append("  ⚠️ 竞品数量较多，建议优化产品陈列位置")
    
    high_conf_count = sum(1 for box in analysis["valid_boxes"] if box.get("confidence", 0) >= 0.8)
    if high_conf_count >= stats['valid_detections'] * 0.7:
        report.append("  ✓ 检测置信度整体较高，结果可靠")
    else:
        report.append("  ⚠️ 部分检测置信度较低，建议人工复核")
    
    report.append("")
    report.append("=" * 60)
    
    return "\n".join(report)


def main():
    file_path = "/Users/budtech/Documents/data-agent-chat/backend/data/dataset/yolo_result.txt"
    
    print("正在解析 YOLO 结果文件...")
    data = parse_yolo_result(file_path)
    
    print(f"共检测到 {data['total_boxes']} 个目标")
    print()
    
    # Analyze with 0.5 confidence threshold
    print("分析有效数据 (置信度 ≥ 0.5)...")
    analysis = analyze_detections(data, confidence_threshold=0.5)
    
    # Generate report
    report = generate_analysis_report(analysis)
    print(report)
    
    # Save analysis to JSON
    output_path = "/Users/budtech/Documents/data-agent-chat/backend/data/dataset/analysis_result.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "raw_data": data,
            "analysis": analysis
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细分析结果已保存到: {output_path}")


if __name__ == "__main__":
    main()
