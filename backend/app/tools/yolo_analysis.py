"""YOLO Detection Results Analysis Tools.

These tools analyze YOLO object detection results from shelf images,
providing insights about product detection, confidence scores,
and sales recommendations.
"""

from __future__ import annotations

import base64
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from langchain_core.tools import tool

# VLM support (optional dependency)
try:
    from langchain_core.messages import HumanMessage
    from app.llm import get_chat_model
    HAS_VLM = True
except ImportError:
    HAS_VLM = False


# ---- VLM Prompts (centralized for easy maintenance) ----

PROMPT_SINGLE_TAG = (
    "这是一个货架商品的价签图片，请识别以下信息：\n"
    "1. 价格（如果有）\n"
    "2. 促销信息（如果有）\n\n"
    "请以 JSON 格式返回，只返回 JSON，不要其他文字：\n"
    '{"price": "价格字符串", "promotion": "促销信息字符串"}'
)

PROMPT_WHOLE_IMAGE = (
    "这是一张货架商品图片，图片上有多个价签。"
    "请识别图片中所有可见的价签，并提取每个价签的：\n"
    "1. 价格\n"
    "2. 促销信息\n"
    "3. 在图片中的大致位置（左上角和右下角坐标，像素）\n\n"
    "请以 JSON 数组格式返回，只返回 JSON，不要其他文字：\n"
    '[{"price": "价格", "promotion": "促销信息", '
    '"location": {"x1": 0, "y1": 0, "x2": 0, "y2": 0}}]'
)


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
    
    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2
    
    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2
    
    @property
    def width(self) -> float:
        return self.x2 - self.x1
    
    @property
    def height(self) -> float:
        return self.y2 - self.y1
    
    @property
    def area(self) -> float:
        return self.width * self.height


@dataclass
class PriceTagInfo:
    """Price tag information with optional OCR data."""
    box: DetectionBox
    ocr_text: str = ""
    price: str = ""
    promotion_info: str = ""
    has_ocr_data: bool = False
    linked_product: Optional['ProductInfo'] = None


@dataclass
class ProductInfo:
    """Product information with optional linked price tag."""
    box: DetectionBox
    product_type: str  # "main" or "competitor"
    price_tag: Optional[PriceTagInfo] = None
    
    @property
    def has_price_info(self) -> bool:
        return self.price_tag is not None and self.price_tag.has_ocr_data


@dataclass
class LayoutAnalysis:
    """Layout analysis results."""
    main_product_in_center: bool
    main_product_area_ratio: float
    competitor_area_ratio: float
    center_region: Tuple[float, float, float, float]  # x1, y1, x2, y2
    main_products_in_center: int
    competitors_in_center: int


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
    main_products: List[ProductInfo]
    competitors: List[ProductInfo]
    layout_analysis: Optional[LayoutAnalysis]


def parse_yolo_result(content: str) -> List[Dict[str, Any]]:
    """Parse YOLO result string and extract detection boxes.

    Args:
        content: Raw YOLO output string

    Returns:
        List of detection box dictionaries
    """
    # Extract the boxes array using regex
    boxes_match = re.search(r'boxes:\s*\[(.*?)\],\s*accelerator', content, re.DOTALL)
    if not boxes_match:
        # Try alternative pattern
        boxes_match = re.search(r'\[(\s*\{.*?\}\s*,?)*\s*\]', content, re.DOTALL)
    
    if not boxes_match:
        return []
    
    boxes_str = boxes_match.group(1) if boxes_match.groups() else boxes_match.group(0)
    
    # Parse each box manually with better handling
    boxes = []
    
    # Split into individual box strings by tracking braces
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
            # Extract key-value pairs
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
                    box[key] = value
            
            # Map to consistent keys
            if 'class' in box and 'className' not in box:
                box['className'] = box['class']
            elif 'className' in box and 'class' not in box:
                box['class'] = box['className']
            
            if box:
                boxes.append(box)
            
        except Exception:
            continue
    
    return boxes


def calculate_iou(box1: DetectionBox, box2: DetectionBox) -> float:
    """Calculate Intersection over Union between two boxes."""
    x1 = max(box1.x1, box2.x1)
    y1 = max(box1.y1, box2.y1)
    x2 = min(box1.x2, box2.x2)
    y2 = min(box1.y2, box2.y2)
    
    if x1 >= x2 or y1 >= y2:
        return 0
    
    intersection_area = (x2 - x1) * (y2 - y1)
    union_area = box1.area + box2.area - intersection_area
    
    return intersection_area / union_area if union_area > 0 else 0


def find_nearest_price_tag(
    product_box: DetectionBox, 
    price_tags: List[PriceTagInfo],
    max_distance: float = 300
) -> Optional[PriceTagInfo]:
    """Find the nearest price tag for a product.

    Args:
        product_box: The product detection box
        price_tags: List of price tags
        max_distance: Maximum distance to consider (pixels)

    Returns:
        Nearest price tag if found, None otherwise
    """
    best_price_tag: Optional[PriceTagInfo] = None
    best_distance: float = float('inf')
    
    for price_tag in price_tags:
        # Skip already linked price tags
        if price_tag.linked_product is not None:
            continue
        
        # Calculate distance between centers
        dx = product_box.center_x - price_tag.box.center_x
        dy = product_box.center_y - price_tag.box.center_y
        distance = (dx ** 2 + dy ** 2) ** 0.5
        
        # Also consider vertical alignment (price tag should be below/above product)
        vertical_alignment = abs(product_box.center_x - price_tag.box.center_x)
        
        # Combine distance and vertical alignment
        score = distance + vertical_alignment * 0.5
        
        if score < best_distance and score < max_distance:
            best_distance = score
            best_price_tag = price_tag
    
    return best_price_tag


def link_products_to_price_tags(
    main_products: List[DetectionBox],
    competitors: List[DetectionBox],
    price_tags: List[PriceTagInfo],
    max_distance: float = 300
) -> Tuple[List[ProductInfo], List[ProductInfo]]:
    """Link products to their nearest price tags.

    Args:
        main_products: List of main product boxes
        competitors: List of competitor boxes
        price_tags: List of price tag info
        max_distance: Maximum linking distance

    Returns:
        Tuple of (main product infos, competitor infos)
    """
    main_product_infos = []
    competitor_infos = []
    
    # Process main products
    for box in main_products:
        price_tag = find_nearest_price_tag(box, price_tags, max_distance)
        product_info = ProductInfo(box=box, product_type="main", price_tag=price_tag)
        if price_tag:
            price_tag.linked_product = product_info
        main_product_infos.append(product_info)
    
    # Process competitors
    for box in competitors:
        price_tag = find_nearest_price_tag(box, price_tags, max_distance)
        product_info = ProductInfo(box=box, product_type="competitor", price_tag=price_tag)
        if price_tag:
            price_tag.linked_product = product_info
        competitor_infos.append(product_info)
    
    return main_product_infos, competitor_infos


def analyze_layout(
    main_products: List[ProductInfo],
    competitors: List[ProductInfo],
    image_size: Optional[Tuple[float, float]] = None
) -> LayoutAnalysis:
    """Analyze the shelf layout.

    Args:
        main_products: List of main product infos
        competitors: List of competitor infos
        image_size: Optional (width, height) of the image, auto-detected if None

    Returns:
        Layout analysis results
    """
    # Auto-detect image size from normalized coordinates if available
    all_boxes = [p.box for p in main_products] + [p.box for p in competitors]
    
    if not all_boxes:
        return LayoutAnalysis(
            main_product_in_center=False,
            main_product_area_ratio=0,
            competitor_area_ratio=0,
            center_region=(0, 0, 1, 1),
            main_products_in_center=0,
            competitors_in_center=0
        )
    
    # Find min/max coordinates to determine image size
    if image_size is None:
        min_x = min(b.x1 for b in all_boxes)
        max_x = max(b.x2 for b in all_boxes)
        min_y = min(b.y1 for b in all_boxes)
        max_y = max(b.y2 for b in all_boxes)
    else:
        min_x, min_y = 0, 0
        max_x, max_y = image_size
    
    # Define center region (middle 50% of image)
    center_x1 = min_x + (max_x - min_x) * 0.25
    center_x2 = min_x + (max_x - min_x) * 0.75
    center_y1 = min_y + (max_y - min_y) * 0.25
    center_y2 = min_y + (max_y - min_y) * 0.75
    
    center_region = (center_x1, center_y1, center_x2, center_y2)
    
    # Count products in center
    def is_in_center(box: DetectionBox) -> bool:
        # Check if center point is in center region
        cx = box.center_x
        cy = box.center_y
        return center_x1 <= cx <= center_x2 and center_y1 <= cy <= center_y2
    
    main_in_center = sum(1 for p in main_products if is_in_center(p.box))
    competitors_in_center = sum(1 for p in competitors if is_in_center(p.box))
    
    # Calculate area ratios
    main_area = sum(p.box.area for p in main_products)
    competitor_area = sum(p.box.area for p in competitors)
    total_area = main_area + competitor_area
    
    main_area_ratio = main_area / total_area if total_area > 0 else 0
    competitor_area_ratio = competitor_area / total_area if total_area > 0 else 0
    
    # Determine if main products are dominant in center
    main_product_in_center = main_in_center > competitors_in_center or (
        main_in_center > 0 and main_area_ratio > 0.6
    )
    
    return LayoutAnalysis(
        main_product_in_center=main_product_in_center,
        main_product_area_ratio=main_area_ratio,
        competitor_area_ratio=competitor_area_ratio,
        center_region=center_region,
        main_products_in_center=main_in_center,
        competitors_in_center=competitors_in_center
    )


def _find_shelf_image(dataset_dir: str) -> Optional[str]:
    """Find the shelf image file in the dataset directory.

    Args:
        dataset_dir: Path to dataset directory

    Returns:
        Path to the image file, or None if not found
    """
    if not dataset_dir:
        return None

    dir_path = Path(dataset_dir)
    if not dir_path.exists():
        return None

    image_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]
    for ext in image_extensions:
        for img_path in sorted(dir_path.glob(f"*{ext}")):
            return str(img_path)

    return None


def crop_price_tag_image(
    image_path: str,
    box: DetectionBox,
    output_path: Optional[str] = None
) -> Optional[str]:
    """Crop the price tag region from the shelf image.

    Args:
        image_path: Path to the shelf image
        box: Price tag detection box
        output_path: Optional path to save cropped image (if None, no save)

    Returns:
        Base64 encoded cropped image, or None on failure
    """
    try:
        from PIL import Image
        import io as _io

        with Image.open(image_path) as img:
            # Convert coordinates to integers, clamp to image bounds
            x1 = max(0, int(box.x1))
            y1 = max(0, int(box.y1))
            x2 = min(img.width, int(box.x2))
            y2 = min(img.height, int(box.y2))

            if x2 <= x1 or y2 <= y1:
                return None

            cropped = img.crop((x1, y1, x2, y2))

            # Upscale small crops for better OCR accuracy
            min_size = 200
            if cropped.width < min_size or cropped.height < min_size:
                scale = max(min_size / max(cropped.width, 1), min_size / max(cropped.height, 1))
                new_size = (int(cropped.width * scale), int(cropped.height * scale))
                cropped = cropped.resize(new_size, Image.LANCZOS)

            if output_path:
                cropped.save(output_path)

            # Convert to base64
            buffer = _io.BytesIO()
            cropped.convert("RGB").save(buffer, format="JPEG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"[yolo_analysis] Crop price tag failed: {e}")
        return None


def ocr_price_tag_image(
    image_base64: str,
    image_url: Optional[str] = None
) -> Dict[str, str]:
    """Use VLM to recognize price and promotion info from a price tag image.

    Args:
        image_base64: Base64 encoded price tag image
        image_url: Optional image URL/path (used directly if base64 unavailable)

    Returns:
        Dict with keys: {"price": str, "promotion": str}
    """
    if not HAS_VLM:
        return {"price": "", "promotion": ""}

    try:
        messages = [
            HumanMessage(
                content=[
                    {"type": "text", "text": PROMPT_SINGLE_TAG},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                    },
                ]
            )
        ]

        model = get_chat_model(temperature=0)
        response = model.invoke(messages)
        content = response.content.strip()

        # Extract JSON from response
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
            return {
                "price": str(parsed.get("price", "")),
                "promotion": str(parsed.get("promotion", "")),
            }
        return {"price": "", "promotion": ""}
    except Exception as e:
        print(f"[yolo_analysis] OCR recognize failed: {e}")
        return {"price": "", "promotion": ""}


def ocr_price_tag_file(image_path: str) -> Dict[str, str]:
    """OCR a single price tag image file (already cropped by user).

    Directly reads the file, converts to base64, and calls VLM to recognize
    price and promotion info. Returns one result.

    Args:
        image_path: Path to a single cropped price tag image (e.g. 价签.png)

    Returns:
        Dict with keys: {"price": str, "promotion": str}
    """
    img_path = Path(image_path)
    if not img_path.exists():
        print(f"[yolo_analysis] Price tag image not found: {image_path}")
        return {"price": "", "promotion": ""}

    try:
        with open(img_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")
        return ocr_price_tag_image(img_base64)
    except Exception as e:
        print(f"[yolo_analysis] ocr_price_tag_file failed: {e}")
        return {"price": "", "promotion": ""}


def ocr_shelf_image_price_tags(
    shelf_image_path: str,
    price_tag_boxes: List[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Use VLM to recognize ALL price tags from the whole shelf image at once.

    Unlike ocr_price_tag_image (single cropped tag), this method feeds the
    entire shelf image to the VLM and asks it to locate and OCR every price
    tag in one call. Useful for comparing whole-image recognition vs.
    YOLO-crop-then-recognize (Plan B).

    Args:
        shelf_image_path: Path to the whole shelf image
        price_tag_boxes: Optional list of YOLO-detected price tag boxes
            (used to hint the VLM about expected tag count/locations).
            Each item should contain x1, y1, x2, y2 coordinates.

    Returns:
        List of dicts, each: {
            "price": str, "promotion": str,
            "location": {"x1": ..., "y1": ..., "x2": ..., "y2": ...}
        }
    """
    if not HAS_VLM:
        return []

    img_path = Path(shelf_image_path)
    if not img_path.exists():
        print(f"[yolo_analysis] Shelf image not found: {shelf_image_path}")
        return []

    try:
        with open(img_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        # Build hint about expected tag locations
        location_hint = ""
        if price_tag_boxes:
            location_hint = f"\n\n参考信息：YOLO 检测到约 {len(price_tag_boxes)} 个价签位置。"
            try:
                from PIL import Image as _Img
                with _Img.open(img_path) as im:
                    img_w, img_h = im.size
                coords_str = []
                for i, b in enumerate(price_tag_boxes[:10]):
                    coords_str.append(
                        f"  价签{i+1}: ({b['x1']:.0f},{b['y1']:.0f})-({b['x2']:.0f},{b['y2']:.0f})"
                    )
                location_hint += " 检测框坐标(像素):\n" + "\n".join(coords_str)
                location_hint += f"\n图片尺寸: {img_w}x{img_h}"
            except Exception:
                pass

        prompt = PROMPT_WHOLE_IMAGE + location_hint

        messages = [
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                    },
                ]
            )
        ]

        model = get_chat_model(temperature=0)
        response = model.invoke(messages)
        content = response.content.strip()

        # Extract JSON array from response
        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
            if isinstance(parsed, list):
                results = []
                for item in parsed:
                    results.append({
                        "price": str(item.get("price", "")),
                        "promotion": str(item.get("promotion", "")),
                        "location": item.get("location", {}),
                    })
                print(f"[yolo_analysis] Whole-image OCR: detected {len(results)} price tags")
                return results
        # Fallback: try single object
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
            return [{
                "price": str(parsed.get("price", "")),
                "promotion": str(parsed.get("promotion", "")),
                "location": parsed.get("location", {}),
            }]
        print(f"[yolo_analysis] Whole-image OCR: no JSON parsed from response")
        return []
    except Exception as e:
        print(f"[yolo_analysis] Whole-image OCR failed: {e}")
        return []


def ocr_price_tags(
    price_tags: List[PriceTagInfo],
    dataset_dir: str,
    max_tags: int = 10
) -> List[PriceTagInfo]:
    """OCR process price tags: crop from shelf image, then VLM recognize.

    Only processes price tags without existing OCR data.

    Args:
        price_tags: List of PriceTagInfo to process
        dataset_dir: Dataset directory containing the shelf image
        max_tags: Maximum number of price tags to OCR (cost control)

    Returns:
        Updated list of PriceTagInfo with OCR data filled in
    """
    if not price_tags:
        return price_tags

    # Find the shelf image
    image_path = _find_shelf_image(dataset_dir)
    if not image_path:
        print(f"[yolo_analysis] No shelf image found in {dataset_dir}")
        return price_tags

    # Sort by confidence, process highest confidence tags first
    tags_to_process = [t for t in price_tags if not t.has_ocr_data]
    tags_to_process.sort(key=lambda t: t.box.confidence, reverse=True)
    tags_to_process = tags_to_process[:max_tags]

    processed_count = 0
    for tag in tags_to_process:
        image_base64 = crop_price_tag_image(image_path, tag.box)
        if not image_base64:
            continue

        ocr_result = ocr_price_tag_image(image_base64)
        if ocr_result.get("price") or ocr_result.get("promotion"):
            tag.price = ocr_result.get("price", "")
            tag.promotion_info = ocr_result.get("promotion", "")
            tag.ocr_text = f"price={tag.price}; promotion={tag.promotion_info}"
            tag.has_ocr_data = True
            processed_count += 1

    print(f"[yolo_analysis] OCR processed {processed_count}/{len(tags_to_process)} price tags")
    return price_tags


def analyze_detections(
    boxes: List[Dict[str, Any]],
    confidence_threshold: float = 0.5,
    price_tag_keywords: List[str] = None,
    dataset_dir: Optional[str] = None,
    max_ocr_tags: int = 10
) -> AnalysisResult:
    """Analyze detections with confidence threshold filtering.

    New categorization logic:
    - Price tags: Identified by specific keywords
    - Main products: NON-price-tag items ABOVE confidence threshold
    - Competitors: NON-price-tag items BELOW confidence threshold

    Args:
        boxes: List of detection boxes
        confidence_threshold: Minimum confidence score for main products
        price_tag_keywords: Keywords to identify price tags
        dataset_dir: Optional dataset directory containing shelf image,
                     enables VLM OCR of price tags (Plan B: crop + VLM)
        max_ocr_tags: Max number of price tags to OCR (cost control)

    Returns:
        AnalysisResult object with detailed analysis
    """
    if price_tag_keywords is None:
        price_tag_keywords = ["价签", "price", "Price", "PRICE", "标签"]
    
    # Categorize - separate price tags first
    price_tags = []
    non_price_boxes = []
    
    for box in boxes:
        class_name = box.get("className", "")
        
        # Check if it's a price tag
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
    
    # Now categorize non-price boxes by confidence threshold
    main_product_boxes = []
    competitor_boxes = []
    
    for box in non_price_boxes:
        confidence = box.get("confidence", 0)
        if confidence >= confidence_threshold:
            main_product_boxes.append(box)
        else:
            competitor_boxes.append(box)
    
    # Valid boxes = main products + price tags
    valid_boxes = main_product_boxes + price_tags
    low_conf_boxes = competitor_boxes
    
    # Calculate statistics
    product_distribution = defaultdict(int)
    for box in valid_boxes:
        class_name = box.get("className", "Unknown")
        product_distribution[class_name] += 1
    
    # Confidence statistics
    confidences = [box.get("confidence", 0) for box in boxes]
    confidence_stats = {
        "min": min(confidences) if confidences else 0,
        "max": max(confidences) if confidences else 0,
        "mean": sum(confidences) / len(confidences) if confidences else 0
    }
    
    # Convert to DetectionBox objects and PriceTagInfo
    valid_detection_boxes = []
    price_tag_infos = []
    main_product_detection_boxes = []
    competitor_detection_boxes = []
    
    # Process main products
    for box in main_product_boxes:
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
            main_product_detection_boxes.append(detection_box)
        except Exception:
            continue
    
    # Process competitors
    for box in competitor_boxes:
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
            competitor_detection_boxes.append(detection_box)
        except Exception:
            continue
    
    # Process price tags with OCR support
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
            
            # Create PriceTagInfo with optional OCR data
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
    
    # VLM OCR: crop price tags from shelf image and recognize (Plan B)
    if dataset_dir and price_tag_infos:
        price_tag_infos = ocr_price_tags(price_tag_infos, dataset_dir, max_ocr_tags)
    
    # Link products to price tags
    main_product_infos, competitor_infos = link_products_to_price_tags(
        main_product_detection_boxes,
        competitor_detection_boxes,
        price_tag_infos
    )
    
    # Analyze layout
    layout_analysis = analyze_layout(main_product_infos, competitor_infos)
    
    return AnalysisResult(
        total_detections=len(boxes),
        valid_detections=len(valid_boxes),
        low_confidence_detections=len(low_conf_boxes),
        confidence_threshold=confidence_threshold,
        main_products_count=len(main_product_infos),
        competitors_count=len(competitor_infos),
        price_tags_count=len(price_tag_infos),
        product_distribution=dict(product_distribution),
        confidence_stats=confidence_stats,
        valid_boxes=valid_detection_boxes,
        price_tags=price_tag_infos,
        main_products=main_product_infos,
        competitors=competitor_infos,
        layout_analysis=layout_analysis
    )


def _price_tag_summary(price_tag: Optional[PriceTagInfo]) -> Optional[Dict[str, Any]]:
    """Flatten a linked price tag into a JSON-safe summary (no circular refs)."""
    if price_tag is None:
        return None
    return {
        "price": price_tag.price,
        "promotion_info": price_tag.promotion_info,
        "ocr_text": price_tag.ocr_text,
        "has_ocr_data": price_tag.has_ocr_data,
        "tag_confidence": price_tag.box.confidence,
    }


def _to_dict(obj, visited=None):
    """Convert dataclass objects to JSON-serializable dictionaries."""
    if visited is None:
        visited = set()
    
    # 防止循环引用
    obj_id = id(obj)
    if obj_id in visited:
        return None
    visited.add(obj_id)
    
    try:
        if hasattr(obj, "__dict__"):
            result = {}
            for key, value in obj.__dict__.items():
                if key.startswith("_"):
                    continue
                # Flatten linked price tag (avoid circular reference)
                if key == "price_tag":
                    summary = _price_tag_summary(value)
                    if summary is not None:
                        result["price_tag"] = summary
                    continue
                # Skip back-reference to avoid circular refs
                if key == "linked_product":
                    continue
                if isinstance(value, list):
                    result[key] = [_to_dict(item, visited.copy()) for item in value]
                elif value is not None and hasattr(value, "__dict__"):
                    result[key] = _to_dict(value, visited.copy())
                else:
                    result[key] = value
            return result
        elif isinstance(obj, (list, tuple)):
            return [_to_dict(item, visited.copy()) for item in obj]
        elif isinstance(obj, dict):
            return {k: _to_dict(v, visited.copy()) for k, v in obj.items()}
        else:
            return obj
    finally:
        visited.remove(obj_id)


def analyze_yolo_content(
    yolo_content: str,
    confidence_threshold: float = 0.5,
    dataset_dir: Optional[str] = None,
    max_ocr_tags: int = 10
) -> Dict[str, Any]:
    """Complete analysis pipeline for YOLO content.

    Args:
        yolo_content: Raw YOLO output string
        confidence_threshold: Minimum confidence threshold
        dataset_dir: Optional dataset directory with shelf image for VLM OCR
        max_ocr_tags: Max price tags to OCR (cost control)

    Returns:
        JSON-serializable dictionary with structured analysis results
    """
    # Parse the YOLO result
    boxes = parse_yolo_result(yolo_content)
    
    # Analyze the detections (with optional VLM OCR of price tags)
    analysis = analyze_detections(
        boxes,
        confidence_threshold,
        dataset_dir=dataset_dir,
        max_ocr_tags=max_ocr_tags
    )
    
    # Convert to JSON-serializable format
    return {
        "analysis": _to_dict(analysis),
        "raw_boxes": boxes
    }


@tool
def analyze_yolo_results(
    yolo_content: str,
    confidence_threshold: float = 0.5,
    dataset_dir: str = ""
) -> str:
    """Analyze YOLO shelf detection results.

    This tool processes YOLO object detection output from shelf images,
    providing structured data about product counts, competitor analysis,
    price tag detection (with VLM OCR if dataset_dir provided), and layout analysis.

    Args:
        yolo_content: Raw YOLO detection result string containing boxes array
        confidence_threshold: Minimum confidence score for valid detections (default: 0.5)
        dataset_dir: Optional directory path containing the shelf image,
                     enables VLM OCR of price tags (price/promotion recognition)

    Returns:
        JSON string with structured analysis results
    """
    try:
        result = analyze_yolo_content(
            yolo_content,
            confidence_threshold,
            dataset_dir=dataset_dir or None
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


YOLO_TOOLS = [analyze_yolo_results]
