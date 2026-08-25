#!/usr/bin/env python3
"""Test the updated categorization logic and OCR price tag support."""

import sys
import os

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Copy of the updated functions for testing
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
class PriceTagInfo:
    """Price tag information with optional OCR data."""
    box: DetectionBox
    ocr_text: str = ""
    price: str = ""
    promotion_info: str = ""
    has_ocr_data: bool = False


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
    price_tags: List[PriceTagInfo]
    recommendations: List[str]


def parse_yolo_result(content: str) -> List[Dict[str, Any]]:
    """Parse YOLO result string and extract detection boxes."""
    # Extract the boxes array using regex
    boxes_match = re.search(r'boxes:\s*\[(.*?)\],\s*accelerator', content, re.DOTALL)
    if not boxes_match:
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
    price_tag_keywords: List[str] = None
) -> AnalysisResult:
    """Analyze detections with new categorization logic."""
    if price_tag_keywords is None:
        price_tag_keywords = ["价签", "price", "Price", "PRICE", "标签"]
    
    # Categorize - separate price tags first
    price_tags = []
    non_price_boxes = []
    
    for box in boxes:
        class_name = box.get("className", "")
        
        is_price_tag = False
        if class_name:
            for keyword in price_tag_keywords:
                if keyword in class_name:
                    is_price_tag = True
                    break
        
        if is_price_tag:
            price_tags.append(box)
        else:
            non_price_boxes.append(box)
    
    # Categorize non-price boxes by confidence threshold
    main_products = []
    competitors = []
    
    for box in non_price_boxes:
        confidence = box.get("confidence", 0)
        if confidence >= confidence_threshold:
            main_products.append(box)
        else:
            competitors.append(box)
    
    # Valid boxes = main products + price tags
    valid_boxes = main_products + price_tags
    low_conf_boxes = competitors
    
    # Calculate statistics
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
    
    # Convert boxes
    valid_detection_boxes = []
    price_tag_infos = []
    
    for box in main_products:
        try:
            detection_box = DetectionBox(
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
            )
            valid_detection_boxes.append(detection_box)
        except Exception:
            continue
    
    for box in price_tags:
        try:
            detection_box = DetectionBox(
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
            )
            valid_detection_boxes.append(detection_box)
            
            price_tag_info = PriceTagInfo(
                box=detection_box,
                ocr_text=box.get("ocr_text", ""),
                price=box.get("price", ""),
                promotion_info=box.get("promotion_info", ""),
                has_ocr_data=box.get("has_ocr_data", False) or bool(box.get("ocr_text", ""))
            )
            price_tag_infos.append(price_tag_info)
        except Exception:
            continue
    
    # Generate recommendations
    recommendations = []
    if len(competitors) > 0:
        recommendations.append(f"⚠️ 检测到 {len(competitors)} 个竞品（低置信度）")
    
    if len(price_tags) == 0:
        recommendations.append("⚠️ 未检测到价签")
    else:
        price_tags_with_ocr = len([pt for pt in price_tag_infos if pt.has_ocr_data])
        if price_tags_with_ocr > 0:
            recommendations.append(f"✓ 检测到 {len(price_tags)} 个价签，其中 {price_tags_with_ocr} 个有 OCR 数据")
        else:
            recommendations.append(f"✓ 检测到 {len(price_tags)} 个价签，建议进行 OCR 识别")
    
    if len(main_products) > len(competitors):
        recommendations.append("✓ 主要产品占据优势")
    elif len(main_products) < len(competitors):
        recommendations.append("⚠️ 竞品数量较多")
    
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
        price_tags=price_tag_infos,
        recommendations=recommendations
    )


def format_analysis_report(result: AnalysisResult) -> str:
    """Format analysis report."""
    report = []
    report.append("=" * 60)
    report.append("YOLO 货架检测分析报告 (新分类逻辑)")
    report.append("=" * 60)
    report.append("")
    
    report.append("1. 检测统计")
    report.append("-" * 40)
    report.append(f"总检测数量: {result.total_detections}")
    report.append(f"有效检测 (置信度 ≥ {result.confidence_threshold}): {result.valid_detections}")
    report.append(f"低置信度检测: {result.low_confidence_detections} 个")
    report.append("")
    
    report.append("2. 产品分类统计")
    report.append("-" * 40)
    report.append(f"主要产品数量: {result.main_products_count}")
    report.append(f"竞品数量: {result.competitors_count}")
    report.append(f"价签数量: {result.price_tags_count}")
    report.append("")
    
    report.append("3. 分类逻辑说明")
    report.append("-" * 40)
    report.append("  - 主要产品: 非价签 + 置信度 ≥ 阈值")
    report.append("  - 竞品: 非价签 + 置信度 < 阈值")
    report.append("  - 价签: 通过关键词识别")
    report.append("")
    
    report.append("4. 产品分布详情")
    report.append("-" * 40)
    for product, count in sorted(result.product_distribution.items(), key=lambda x: x[1], reverse=True):
        report.append(f"  {product}: {count} 个")
    report.append("")
    
    report.append("5. 分析建议")
    report.append("-" * 40)
    for rec in result.recommendations:
        report.append(f"  {rec}")
    report.append("")
    
    report.append("=" * 60)
    
    return "\n".join(report)


def main():
    """Test with the sample data."""
    print("=" * 60)
    print("测试新分类逻辑")
    print("=" * 60)
    print()
    
    # Read the sample data
    file_path = "data/dataset/yolo_result.txt"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Parse and analyze
    boxes = parse_yolo_result(content)
    result = analyze_detections(boxes, confidence_threshold=0.5)
    
    # Generate and display report
    report = format_analysis_report(result)
    print(report)
    
    # Let's also test with some sample OCR data
    print("\n" + "=" * 60)
    print("测试 OCR 价签支持")
    print("=" * 60)
    print()
    
    # Create some sample price tags with OCR data
    sample_boxes = boxes.copy()
    
    # Add OCR data to the first price tag
    for box in sample_boxes:
        if box.get("className") == "价签" and box.get("confidence", 0) >= 0.5:
            box["ocr_text"] = "百威啤酒 500ml ¥9.90 促销:买二送一"
            box["price"] = "¥9.90"
            box["promotion_info"] = "买二送一"
            box["has_ocr_data"] = True
            break
    
    # Analyze again with OCR data
    result_with_ocr = analyze_detections(sample_boxes, confidence_threshold=0.5)
    
    print(f"价签总数: {result_with_ocr.price_tags_count}")
    print(f"有OCR数据的价签: {len([pt for pt in result_with_ocr.price_tags if pt.has_ocr_data])}")
    print()
    
    for price_tag in result_with_ocr.price_tags:
        if price_tag.has_ocr_data:
            print("✓ 有OCR数据的价签:")
            if price_tag.price:
                print(f"  价格: {price_tag.price}")
            if price_tag.promotion_info:
                print(f"  促销: {price_tag.promotion_info}")
            if price_tag.ocr_text:
                print(f"  OCR文本: {price_tag.ocr_text}")
        else:
            print("✗ 无OCR数据的价签")


if __name__ == "__main__":
    main()
