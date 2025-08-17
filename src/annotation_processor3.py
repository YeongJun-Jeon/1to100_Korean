import os
import json
from typing import List, Dict, Tuple, Any, Optional
from PIL import Image, ImageDraw
from collections import defaultdict

from .image_cropper import crop_and_mask_image, Bbox
from .config import Config

# --- Type Aliases ---
Component = Dict[str, Any]
LogicalUnit = List[Component]

def _area(b):
    return max(0.0, (b[2]-b[0])) * max(0.0, (b[3]-b[1]))

def _iou(a, b):
    x1 = max(a[0], b[0]); y1 = max(a[1], b[1])
    x2 = min(a[2], b[2]); y2 = min(a[3], b[3])
    inter = max(0.0, x2-x1) * max(0.0, y2-y1)
    if inter <= 0: return 0.0
    ua = _area(a) + _area(b) - inter
    return inter / ua if ua > 0 else 0.0

def _nms(annos: List[Dict[str, Any]], iou_thr: float) -> List[Dict[str, Any]]:
    # simple greedy NMS; assumes 'confidence' may exist; if not, keeps input order
    annos_sorted = sorted(annos, key=lambda d: d.get('confidence', 0.5), reverse=True)
    kept = []
    for a in annos_sorted:
        if all(_iou(a['bbox'], b['bbox']) < iou_thr for b in kept):
            kept.append(a)
    return kept

def _kmeans_two_columns(x_centers: List[float]) -> Optional[Tuple[float, float]]:
    """
    Returns (threshold_x, median_left) using simple median split if sklearn unavailable.
    """
    try:
        from sklearn.cluster import KMeans
        import numpy as np
        X = np.array(x_centers).reshape(-1,1)
        km = KMeans(n_clusters=2, n_init=10, random_state=42).fit(X)
        centers = sorted([c[0] for c in km.cluster_centers_])
        threshold = sum(centers)/2.0
        return threshold, centers[0]
    except Exception:
        if not x_centers: return None
        xs = sorted(x_centers)
        mid = xs[len(xs)//2]
        return mid, xs[0]

def _point_in_bbox(pt, bbox):
    x,y = pt
    return (bbox[0] <= x <= bbox[2]) and (bbox[1] <= y <= bbox[3])

def _center(b):
    return ((b[0]+b[2])/2.0, (b[1]+b[3])/2.0)

def _distance(p, q):
    return ((p[0]-q[0])**2 + (p[1]-q[1])**2) ** 0.5

def _merge_adjacent_blocks(blocks: List[Dict[str, Any]], x_overlap_ratio=0.6, max_vgap_px=80) -> List[Dict[str, Any]]:
    """
    Merge vertically adjacent blocks that likely belong together (e.g., splitted question_block).
    Assumes blocks are pre-sorted by y.
    """
    merged = []
    for b in blocks:
        if not merged:
            merged.append(b); continue
        last = merged[-1]
        # compute overlap in x
        left = max(last['bbox'][0], b['bbox'][0])
        right = min(last['bbox'][2], b['bbox'][2])
        overlap_w = max(0.0, right - left)
        width_ref = max(last['bbox'][2]-last['bbox'][0], 1.0)
        vgap = b['bbox'][1] - last['bbox'][3]
        if (overlap_w / width_ref >= x_overlap_ratio) and (0 <= vgap <= max_vgap_px):
            # union
            new_bbox = (
                min(last['bbox'][0], b['bbox'][0]),
                min(last['bbox'][1], b['bbox'][1]),
                max(last['bbox'][2], b['bbox'][2]),
                max(last['bbox'][3], b['bbox'][3]),
            )
            # merge children/attachments if exist
            children = last.get('children', []) + b.get('children', [])
            attachments = last.get('attachments', []) + b.get('attachments', [])
            last.update({'bbox': new_bbox, 'children': children, 'attachments': attachments})
        else:
            merged.append(b)
    return merged

def process_annotations_from_json(json_file_path: str, base_output_dir: str, config: Config) -> List[LogicalUnit]:
    """
    여러 페이지의 YOLO 어노테이션(JSON)을 받아 후처리 → 컬럼/정렬 →
    question_number 매핑/마스킹 → logical_units 생성 → 크롭 이미지 저장까지 수행.
    픽셀 좌표계를 기준으로 처리합니다.
    """
    with open(json_file_path, 'r', encoding='utf-8') as f:
        pages = json.load(f)

    # 페이지 단위로 처리
    processed_pages: List[List[Dict[str, Any]]] = []
    for page_index, page_data in enumerate(pages):
        image_path = page_data["image_path"]
        try:
            with Image.open(image_path) as img:
                img_w, img_h = img.size
        except Exception:
            img_w = 2000; img_h = 3000  # fallback

        # 1) 기본 필터링 (면적/신뢰도/종횡비)
        raw = []
        for a in page_data["annotations"]:
            bbox = tuple(map(float, a["bbox"]))
            w = max(0.0, bbox[2]-bbox[0]); h = max(0.0, bbox[3]-bbox[1])
            area = w*h
            area_ratio = area / max(1.0, img_w*img_h)
            conf = float(a.get("confidence", 0.5))
            label = a["label"]
            # class-wise thresholds
            min_conf = {"question_number":0.40, "figure":0.50}.get(label, 0.35)
            if conf < min_conf: 
                continue
            if area_ratio < 0.002:
                continue
            # simple aspect rules for question_number
            if label == "question_number":
                ar = (max(w,h)/max(1.0, min(w,h)))
                if ar > 5.0: # too elongated
                    continue
            a = dict(a)
            a.update({"bbox": bbox, "page_index": page_index, "original_image_path": image_path})
            raw.append(a)

        # 2) 클래스별 NMS
        by_cls = defaultdict(list)
        for a in raw:
            by_cls[a["label"]].append(a)
        filtered = []
        for lbl, arr in by_cls.items():
            filtered.extend(_nms(arr, iou_thr=0.5))
        # 3) question_block 분할 병합
        qbs = [a for a in filtered if a["label"]=="question_block"]
        others = [a for a in filtered if a["label"]!="question_block"]
        # sort by y for merging
        qbs = sorted(qbs, key=lambda x: (x["bbox"][1], x["bbox"][0]))
        qbs = _merge_adjacent_blocks(qbs, x_overlap_ratio=0.6, max_vgap_px=int(img_h*0.03))
        filtered = qbs + others

        # 4) 컬럼 판별 (kmeans→fallback)
        x_centers = [ (a["bbox"][0]+a["bbox"][2])/2.0 for a in filtered if a["label"]!="footer" ]
        column_threshold = None
        res = _kmeans_two_columns(x_centers)
        if res:
            threshold_x, _ = res
            column_threshold = threshold_x
        else:
            column_threshold = img_w/2.0

        for a in filtered:
            xc = (a["bbox"][0]+a["bbox"][2])/2.0
            a["column"] = 0 if xc < column_threshold else 1

        # 5) question_number → question_block 매핑
        blocks = [a for a in filtered if a["label"]=="question_block"]
        numbers = [a for a in filtered if a["label"]=="question_number"]
        for b in blocks:
            b["children"] = []
            b["attachments"] = []
        for qn in numbers:
            qn_center = _center(qn["bbox"])
            # prefer containment
            candidate = None
            for b in blocks:
                if _point_in_bbox(qn_center, b["bbox"]):
                    candidate = b; break
            if candidate is None:
                # nearest within same column, else global nearest
                same_col = [b for b in blocks if b["column"]==qn["column"]]
                cands = same_col if same_col else blocks
                if cands:
                    dists = [(b, _distance(_center(b["bbox"]), qn_center)) for b in cands]
                    dists.sort(key=lambda x: x[1])
                    if dists and dists[0][1] <= max(img_h*0.1, 120):  # distance gate
                        candidate = dists[0][0]
            if candidate:
                candidate["children"].append(qn)

        # 6) figure를 가장 가까운 passage 또는 question_block에 부착
        figures = [a for a in filtered if a["label"]=="figure"]
        passages = [a for a in filtered if a["label"]=="passage"]
        for fig in figures:
            fig_center = _center(fig["bbox"])
            cands = blocks + passages
            if not cands: 
                continue
            dists = [(c, _distance(_center(c["bbox"]), fig_center)) for c in cands]
            dists.sort(key=lambda x: x[1])
            host = dists[0][0]
            host.setdefault("attachments", []).append(fig)

        # 정렬 및 보관
        filtered_sorted = sorted(filtered, key=lambda x: (x["column"], x["bbox"][1], x["bbox"][0]))
        processed_pages.append(filtered_sorted)

    # --- 7) 크롭 생성 + logical unit 구성 ---
    os.makedirs(base_output_dir, exist_ok=True)
    debug_output_dir = os.path.join(base_output_dir, "..", "debug_crops")
    os.makedirs(debug_output_dir, exist_ok=True)

    def _crop_component(anno: Dict[str, Any], mask_children: Optional[List[Dict[str, Any]]] = None) -> str:
        label = anno['label']
        bbox = tuple(int(round(c)) for c in anno['bbox'])
        image_path = anno['original_image_path']

        original_image = Image.open(image_path)
        cropped_image = crop_and_mask_image(original_image, bbox)

        # apply masks for question numbers inside question_block
        if label == "question_block" and mask_children:
            rel_masks = []
            for child in mask_children:
                cb = child['bbox']
                rel = (int(round(cb[0]-bbox[0])), int(round(cb[1]-bbox[1])),
                       int(round(cb[2]-bbox[0])), int(round(cb[3]-bbox[1])))
                rel_masks.append(rel)
            if rel_masks:
                draw = ImageDraw.Draw(cropped_image)
                for mb in rel_masks:
                    draw.rectangle(mb, fill="white")

        # save
        label_dir = os.path.join(base_output_dir, label)
        os.makedirs(label_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(image_path))[0]
        idx = len(os.listdir(label_dir))
        out_path = os.path.join(label_dir, f"{base}_{label}_{idx}.png")
        cropped_image.save(out_path)
        return out_path

    logical_units: List[LogicalUnit] = []
    current_unit: LogicalUnit = []

    # Flatten all pages keeping order: by page, then by column (0->1), then y
    all_annos = []
    for arr in processed_pages:
        all_annos.extend(arr)

    for anno in all_annos:
        label = anno["label"]
        # attachments handled later
        if label == "figure" or label == "question_number" or label == "footer":
            continue

        start_new = False
        if label == "header":
            start_new = True
        elif label == "passage":
            if not current_unit or (current_unit and current_unit[-1]['label'] == "question_block"):
                start_new = True
        elif label == "question_block":
            if not current_unit or (current_unit and current_unit[-1]['label'] not in ["passage", "question_block"]):
                start_new = True

        if start_new and current_unit:
            logical_units.append(current_unit)
            current_unit = []

        # create component
        if label == "question_block":
            img_path = _crop_component(anno, mask_children=anno.get("children", []))
            comp: Component = {"label": "question_block", "image_path": img_path, "text_content": ""}
            # crop attachments (e.g., figures)
            atts = []
            for fig in anno.get("attachments", []):
                att_path = _crop_component(fig, mask_children=None)
                atts.append({"label": "figure", "image_path": att_path})
            if atts:
                comp["attachments"] = atts
            current_unit.append(comp)
        else:
            img_path = _crop_component(anno)
            comp = {"label": label, "image_path": img_path, "text_content": ""}
            # if passage has attachments (figures), add them
            atts = []
            for fig in anno.get("attachments", []):
                att_path = _crop_component(fig, mask_children=None)
                atts.append({"label": "figure", "image_path": att_path})
            if atts:
                comp["attachments"] = atts
            current_unit.append(comp)

    if current_unit:
        logical_units.append(current_unit)

    return logical_units