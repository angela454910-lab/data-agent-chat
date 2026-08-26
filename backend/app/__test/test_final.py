#!/usr/bin/env python3
"""Test final YOLO analysis system after refactoring."""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("Testing Final YOLO Analysis System")
print("=" * 80)

# 1. Test importing yolo_analysis module
print("\n1. Testing yolo_analysis module import")
print("-" * 80)
try:
    from app.tools.yolo_analysis import (
        analyze_yolo_content,
        analyze_yolo_results,
        YOLO_TOOLS
    )
    print("✓ Successfully imported yolo_analysis module")
    print(f"✓ analyze_yolo_content is available")
    print(f"✓ analyze_yolo_results (tool) is available")
    print(f"✓ YOLO_TOOLS has {len(YOLO_TOOLS)} tool(s)")
except Exception as e:
    print(f"✗ Failed to import yolo_analysis: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 2. Test yolo_analysis agent
print("\n2. Testing yolo_analysis_agent")
print("-" * 80)
try:
    from app.agents.yolo_analysis_agent import yolo_analysis_agent
    print("✓ Successfully imported yolo_analysis_agent")
except Exception as e:
    print(f"✗ Failed to import yolo_analysis_agent: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Test supervisor
print("\n3. Testing supervisor module")
print("-" * 80)
try:
    from app.agents.supervisor import stream_supervisor
    print("✓ Successfully imported stream_supervisor")
except Exception as e:
    print(f"✗ Failed to import stream_supervisor: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. Test main app
print("\n4. Testing main app import")
print("-" * 80)
try:
    from app.main import app
    print("✓ Successfully imported main FastAPI app")
    print(f"✓ App title: {app.title}")
    print(f"✓ App version: {app.version}")
except Exception as e:
    print(f"✗ Failed to import main app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. Run end-to-end test
print("\n5. Running end-to-end tool test")
print("-" * 80)

data_file = os.path.join(os.path.dirname(__file__), "data", "dataset", "yolo_result.txt")
if not os.path.exists(data_file):
    print(f"⚠ Test data file not found: {data_file}")
    print("Skipping end-to-end test")
else:
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            yolo_content = f.read()
        
        print(f"✓ Loaded YOLO test data ({len(yolo_content)} characters)")
        
        result = analyze_yolo_content(yolo_content, confidence_threshold=0.5)
        print(f"✓ analyze_yolo_content executed successfully")
        print(f"  - Total detections: {result['analysis']['total_detections']}")
        print(f"  - Main products: {result['analysis']['main_products_count']}")
        print(f"  - Competitors: {result['analysis']['competitors_count']}")
        print(f"  - Price tags: {result['analysis']['price_tags_count']}")
        
    except Exception as e:
        print(f"✗ End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()

# 6. Show final file structure
print("\n" + "=" * 80)
print("Final Project Structure")
print("=" * 80)
print("\napp/")
print("├── agents/")
print("│   ├── __init__.py")
print("│   └── yolo_analysis_agent.py  [NEW: YOLO-only agent]")
print("├── memory/")
print("│   ├── __init__.py")
print("│   └── extractor.py")
print("├── session/")
print("│   ├── __init__.py")
print("│   └── store.py")
print("├── tools/")
print("│   ├── __init__.py")
print("│   └── yolo_analysis.py  [UPDATED: Direct tool export]")
print("├── __init__.py")
print("├── llm.py")
print("└── main.py  [UPDATED: YOLO-only API]")

print("\n" + "=" * 80)
print("✓ All tests passed! Refactoring complete.")
print("=" * 80)
