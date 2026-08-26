#!/usr/bin/env python3
"""Test script for YOLO analysis integration."""

from app.tools.yolo_analysis import (
    parse_yolo_result,
    analyze_detections,
    format_analysis_report,
    analyze_yolo_content
)
from app.tools.dataset_tools import analyze_yolo_results, get_yolo_statistics


def test_file_parsing():
    """Test parsing the YOLO result file."""
    print("Testing YOLO file parsing...")
    
    with open("data/dataset/yolo_result.txt", "r", encoding="utf-8") as f:
        content = f.read()
    
    boxes = parse_yolo_result(content)
    print(f"✓ Parsed {len(boxes)} detection boxes")
    
    # Show some sample boxes
    if boxes:
        print("\nSample detections:")
        for i, box in enumerate(boxes[:3], 1):
            print(f"  {i}. {box.get('className', 'Unknown')} - Confidence: {box.get('confidence', 0):.4f}")
    
    return boxes


def test_analysis(boxes):
    """Test detection analysis."""
    print("\nTesting detection analysis...")
    
    analysis = analyze_detections(boxes, confidence_threshold=0.5)
    
    print(f"✓ Total detections: {analysis.total_detections}")
    print(f"✓ Valid detections: {analysis.valid_detections}")
    print(f"✓ Main products: {analysis.main_products_count}")
    print(f"✓ Competitors: {analysis.competitors_count}")
    print(f"✓ Price tags: {analysis.price_tags_count}")
    
    return analysis


def test_report_generation(analysis):
    """Test report generation."""
    print("\nTesting report generation...")
    
    report = format_analysis_report(analysis)
    print(report)
    
    return report


def test_tool_functions():
    """Test the integrated tools."""
    print("\nTesting integrated tool functions...")
    
    with open("data/dataset/yolo_result.txt", "r", encoding="utf-8") as f:
        content = f.read()
    
    print("\nTesting analyze_yolo_results:")
    result = analyze_yolo_results(content, 0.5)
    print(result[:500] + "..." if len(result) > 500 else result)
    
    print("\nTesting get_yolo_statistics:")
    stats = get_yolo_statistics(content, 0.5)
    print(stats)


def main():
    """Run all tests."""
    print("=" * 60)
    print("YOLO Analysis Integration Test")
    print("=" * 60)
    
    # Test 1: File parsing
    boxes = test_file_parsing()
    
    # Test 2: Analysis
    analysis = test_analysis(boxes)
    
    # Test 3: Report generation
    report = test_report_generation(analysis)
    
    # Test 4: Tool functions
    test_tool_functions()
    
    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
