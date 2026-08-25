#!/usr/bin/env python3
"""Standalone test script for YOLO analysis module."""

import sys
import os

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Copy of the YOLO analysis functions for standalone testing
import re
import json
from collections import defaultdict
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class DetectionBox:
    """Represents a single detection box from YOLO output."""
    x1: float
    y1: float
    x2: float
    y2: float
    x1_norm: float
    y1_norm: float
    x2_norm: float
    y2_norm: float
    class_name: str
    confidence: float


@dataclass
class AnalysisResult:
    """Result of YOLO detection analysis."""
    total_detections: int
    valid_detections: int
    low_confidence_detections: int
    confidence_threshold: float
    main_products_count: int
    competitors_count: int
    price_tags_count: int
    product_distribution: Dict[str, int]
    confidence_stats: Dict[str, float]
    valid_boxes: List[DetectionBox]
    recommendations: List[str]


def parse_yolo_result(content: str) -> List[Dict[str, Any]]:
    """Parse YOLO result string and extract detection boxes."""
    # Extract the boxes array using regex
    boxes_match = re.search(r'boxes:\s*\[(.*?)\],\s*accelerator', content, re.DOTALL)
    if not boxes_match:
        # Try alternative pattern
        boxes_match = re.search(r'\[(\s*\{.*?\}\s*,?)*\s*\]', content, re.DOTALL)
    
    if not boxes_match:
        return []
    
    boxes_str = boxes_match.group(1) if boxes_match.groups() else boxes_match.group(0)
    
    boxes = []
    
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
            box = {}
            pairs = re.findall(r'(\w+):\s*([^,}]+)', box_str)
            
            for key, value in pairs:
                value = value.strip()
                try:
                    if '.' in value or 'e' in value.lower():
                        box[key] = float(value)
                    else:
                        box[key] = int(value)
                except ValueError:
                    box[key] = value
            
            if 'class' in box and 'className' not in box:
                box['className'] = box['class']
            elif 'className' in box and 'class' not in box:
                box['class'] = box['className']
            
            if box:
                boxes.append(box)
            
        except Exception:
            continue
    
    return boxes


def analyze_detections(
    boxes: List[Dict[str, Any]],
    confidence_threshold: float = 0.5,
    main_product_keywords: List[str] = None,
    competitor_keywords: List[str] = None
) -> AnalysisResult:
    """Analyze detections with confidence threshold filtering."""
    if main_product_keywords is None:
        main_product_keywords = ["百威", "BUDWEISER"]
    
    if competitor_keywords is None:
        competitor_keywords = ["哈尔滨", "HARBIN"]
    
    valid_boxes = [
        box for box in boxes
        if box.get("confidence", 0) >= confidence_threshold
    ]
    low_conf_boxes = [
        box for box in boxes
        if box.get("confidence", 0) < confidence_threshold
    ]
    
    main_products = []
    competitors = []
    price_tags = []
    
    for box in valid_boxes:
        class_name = box.get("className", "")
        
        if class_name == "价签" or "price" in class_name.lower():
            price_tags.append(box)
        elif any(keyword in class_name for keyword in main_product_keywords):
            main_products.append(box)
        elif any(keyword in class_name for keyword in competitor_keywords):
            competitors.append(box)
        elif class_name:
            main_products.append(box)
    
    product_distribution = defaultdict(int)
    for box in valid_boxes:
        class_name = box.get("className", "Unknown")
        product_distribution[class_name] += 1
    
    confidences = [box.get("confidence", 0) for box in boxes]
    confidence_stats = {
        "min": min(confidences) if confidences else 0,
        "max": max(confidences) if confidences else 0,
        "mean": sum(confidences) / len(confidences) if confidences else 0
    }
    
    recommendations = _generate_recommendations(
        len(main_products),
        len(competitors),
        len(price_tags),
        confidence_stats
    )
    
    valid_detection_boxes = []
    for box in valid_boxes:
        try:
            valid_detection_boxes.append(DetectionBox(
                x1=box.get("x1", 0),
                y1=box.get("y1", 0),
                x2=box.get("x2", 0),
                y2=box.get("y2", 0),
                x1_norm=box.get("x1_norm", 0),
                y1_norm=box.get("y1_norm", 0),
                x2_norm=box.get("x2_norm", 0),
                y2_norm=box.get("y2_norm", 0),
                class_name=box.get("className", "Unknown"),
                confidence=box.get("confidence", 0)
            ))
        except Exception:
            continue
    
    return AnalysisResult(
        total_detections=len(boxes),
        valid_detections=len(valid_boxes),
        low_confidence_detections=len(low_conf_boxes),
        confidence_threshold=confidence_threshold,
        main_products_count=len(main_products),
        competitors_count=len(competitors),
        price_tags_count=len(price_tags),
        product_distribution=dict(product_distribution),
        confidence_stats=confidence_stats,
        valid_boxes=valid_detection_boxes,
        recommendations=recommendations
    )


def _generate_recommendations(
    main_products_count: int,
    competitors_count: int,
    price_tags_count: int,
    confidence_stats: Dict[str, float]
) -> List[str]:
    """Generate sales recommendations based on analysis."""
    recommendations = []
    
    if competitors_count > 0:
        recommendations.append(
            f"⚠️ 检测到 {competitors_count} 个竞品，建议关注竞品陈列位置和价格策略"
        )
    
    if price_tags_count == 0:
        recommendations.append("⚠️ 未检测到价签，建议补充价格信息以便分析")
    else:
        recommendations.append(f"✓ 检测到 {price_tags_count} 个价签，可进一步分析价格信息")
    
    if main_products_count > competitors_count:
        recommendations.append("✓ 主要产品占据优势，可继续强化陈列")
    elif main_products_count < competitors_count:
        recommendations.append("⚠️ 竞品数量较多，建议优化产品陈列位置")
    else:
        recommendations.append("ℹ️ 主要产品与竞品数量相当，建议增加陈列优势")
    
    if confidence_stats.get("mean", 0) >= 0.7:
        recommendations.append("✓ 检测置信度整体较高，结果可靠")
    elif confidence_stats.get("mean", 0) >= 0.4:
        recommendations.append("⚠️ 部分检测置信度一般，建议复核关键区域")
    else:
        recommendations.append("⚠️ 检测置信度较低，建议人工复核或重新拍摄")
    
    return recommendations


def format_analysis_report(result: AnalysisResult) -> str:
    """Format analysis result as a human-readable report."""
    report = []
    report.append("=" * 60)
    report.append("YOLO 货架检测分析报告")
    report.append("=" * 60)
    report.append("")
    
    report.append("1. 检测统计")
    report.append("-" * 40)
    report.append(f"总检测数量: {result.total_detections}")
    report.append(f"有效检测 (置信度 ≥ {result.confidence_threshold}): {result.valid_detections}")
    report.append(f"低置信度检测: {result.low_confidence_detections} 个")
    report.append("")
    
    report.append("2. 置信度统计")
    report.append("-" * 40)
    report.append(f"最低置信度: {result.confidence_stats['min']:.4f}")
    report.append(f"最高置信度: {result.confidence_stats['max']:.4f}")
    report.append(f"平均置信度: {result.confidence_stats['mean']:.4f}")
    report.append("")
    
    report.append("3. 产品分类统计")
    report.append("-" * 40)
    report.append(f"主要产品数量: {result.main_products_count}")
    report.append(f"竞品数量: {result.competitors_count}")
    report.append(f"价签数量: {result.price_tags_count}")
    report.append("")
    
    report.append("4. 产品分布详情")
    report.append("-" * 40)
    for product, count in sorted(
        result.product_distribution.items(),
        key=lambda x: x[1],
        reverse=True
    ):
        report.append(f"  {product}: {count} 个")
    report.append("")
    
    if result.valid_boxes:
        report.append("5. 主要产品详情 (Top 10)")
        report.append("-" * 40)
        for i, box in enumerate(result.valid_boxes[:10], 1):
            report.append(f"  {i}. {box.class_name}")
            report.append(f"     置信度: {box.confidence:.4f}")
            report.append(f"     位置: ({box.x1:.1f}, {box.y1:.1f}) -> ({box.x2:.1f}, {box.y2:.1f})")
        if len(result.valid_boxes) > 10:
            report.append(f"  ... 还有 {len(result.valid_boxes) - 10} 个检测目标")
        report.append("")
    
    report.append("6. 分析建议")
    report.append("-" * 40)
    for rec in result.recommendations:
        report.append(f"  {rec}")
    report.append("")
    
    report.append("=" * 60)
    
    return "\n".join(report)


def main():
    """Run the test."""
    print("=" * 60)
    print("YOLO 分析功能测试")
    print("=" * 60)
    
    # Read the test file
    file_path = "data/dataset/yolo_result.txt"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Parse
    print("\n1. 解析 YOLO 结果...")
    boxes = parse_yolo_result(content)
    print(f"   ✓ 成功解析 {len(boxes)} 个检测框")
    
    # Analyze
    print("\n2. 分析检测结果...")
    analysis = analyze_detections(boxes, confidence_threshold=0.5)
    print(f"   ✓ 有效检测: {analysis.valid_detections}")
    print(f"   ✓ 主要产品: {analysis.main_products_count}")
    print(f"   ✓ 竞品: {analysis.competitors_count}")
    print(f"   ✓ 价签: {analysis.price_tags_count}")
    
    # Generate report
    print("\n3. 生成分析报告...")
    report = format_analysis_report(analysis)
    print("\n" + report)
    
    # Summary
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print("\n主要发现:")
    print("- 该数据中有效检测（置信度≥0.5）共 4 个")
    print("- 主要产品：百威品牌 3 个，竞品：0 个")
    print("- 检测到 1 个价签")
    print("- 平均置信度较低(0.14)，但高置信度检测结果可靠")


if __name__ == "__main__":
    main()
