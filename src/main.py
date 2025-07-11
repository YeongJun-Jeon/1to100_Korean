import os
from typing import Dict, Any

from .annotation_processor import process_annotations_from_json
from .layout_organizer import shuffle_logical_units
from .pdf_recombiner import recombine_pdf
from .config import PROJECT_ROOT, DPI, PDF_STANDARD_DPI

# --- Configuration ---
CONFIG = {
    # --- 기본 파일 경로 설정 (PROJECT_ROOT를 사용하여 동적으로 생성) ---
    "json_input_path": os.path.join(PROJECT_ROOT, "data", "processed", "sample_annotations.json"),
    "base_cropped_output_dir": os.path.join(PROJECT_ROOT, "data", "processed", "cropped_components"),
    "recombined_pdf_output_path": os.path.join(PROJECT_ROOT, "data", "processed", "recombined_output.pdf"),
    
    # --- 페이지 레이아웃 설정 ---
    "page_size": (842, 1191),        # B4 용지 크기 (가로, 세로). 포인트(pt) 단위.
    "margin": 50,                    # 페이지 전체 여백
    "spacing_between_components": 15,# 컴포넌트(이미지) 사이의 수직 간격

    # --- 머리글(Header) 설정 ---
    "header_y_position": 150,         # 페이지 상단으로부터 머리글 선이 그려질 Y 위치
    "header_line_width": 0.5,        # 머리글 가로선의 두께 (0이면 보이지 않음)

    # --- 2단(Column) 레이아웃 설정 ---
    "two_column_layout": True,       # 2단 레이아웃 사용 여부
    "column_line_width": 0.5,        # 두 열 사이의 세로 구분선 두께 (0이면 보이지 않음)
    
    # --- 이미지 및 텍스트 스케일 설정 ---
    # 원본 이미지(DPI)를 PDF의 포인트(PDF_STANDARD_DPI) 단위에 맞게 축소하는 비율
    "image_scale_factor": 1.0 / (DPI / PDF_STANDARD_DPI), 
    
    # --- 문제 번호(Question Number) 설정 ---
    "start_question_number": 1,
    "question_number_font_size": 12,
    "question_number_offset_x": 10,  # 문제 이미지 왼쪽 상단으로부터 번호가 표시될 X간격
    "question_number_offset_y": 12   # 문제 이미지 왼쪽 상단으로부터 번호가 표시될 Y간격
}

if __name__ == "__main__":
    print("스크립트 실행 시작")

    # 1. JSON 파일에서 어노테이션 처리 및 논리적 단위로 그룹화
    print("\n[1/3] 어노테이션 처리 및 이미지 자르기...")
    logical_units = process_annotations_from_json(
        CONFIG["json_input_path"],
        CONFIG["base_cropped_output_dir"]
    )
    print(f"-> {len(logical_units)}개의 논리적 단위를 생성했습니다.")

    # 2. 논리적 단위 셔플
    print("\n[2/3] 논리적 단위 셔플하기...")
    shuffled_units = shuffle_logical_units(logical_units)
    print(f"-> {len(shuffled_units)}개의 유닛을 셔플했습니다.")

    # 3. 셔플된 단위들을 새 PDF로 재조합
    print("\n[3/3] PDF 파일로 재조합하기...")
    recombine_pdf(
        CONFIG["recombined_pdf_output_path"],
        shuffled_units,
        CONFIG
    )
    
    print("\n모든 작업이 완료되었습니다.")