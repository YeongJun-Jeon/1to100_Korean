# 프로젝트 진행 상황 요약

**작성일:** 2025년 7월 10일

## 1. Git 및 프로젝트 초기 설정 완료

*   **`.gitignore` 설정:** `data/`, `models/`, `aws/` 디렉터리를 Git 추적에서 제외하도록 `.gitignore` 파일을 설정했습니다.
*   **Git 저장소 초기화 및 GitHub 연동:** 로컬 Git 저장소를 초기화하고, 제공해주신 GitHub 저장소(`https://github.com/Blackbayor/1to100_Korean`)에 성공적으로 초기 커밋을 푸시했습니다. (병합 충돌 및 Git 사용자 정보 설정 문제 해결 완료)
*   **`PROJECT_PLAN.md` 작성 및 업데이트:** MVP 목표(8월 말까지 웹 기반 재조합 및 다운로드 기능 포함)를 반영하여 상세한 마일스톤과 데드라인이 포함된 프로젝트 계획서를 작성하고 업데이트했습니다.

## 2. 핵심 PDF 처리 및 재조합 로직 개발 (MVP 기능)

`src/preprocess.py` 파일을 중심으로 다음과 같은 핵심 기능들을 구현하고 테스트했습니다.

*   **PDF 이미지 변환 해상도 확인:** `src/pdf_processor.py`에서 PDF를 PNG로 변환 시 DPI 설정이 누락된 것을 확인했으나, 현재 개발에는 문제가 없어 추후 서비스 단계에서 고해상도 반영하기로 결정했습니다.
*   **이미지 구획 자르기 및 마스킹 (`crop_and_mask_image`):**
    *   원본 이미지에서 특정 바운딩 박스 영역을 잘라내는 기능 구현.
    *   `question_block` 내의 기존 `question_number` 영역을 흰색으로 마스킹하여 제거하는 기능 구현.
*   **JSON 기반 어노테이션 처리 (`process_annotations_from_json`):**
    *   `sample_annotations.json` 파일(계층 구조 포함)에서 어노테이션 정보를 읽어와 각 구획(header, passage, question_block, figure, footer 등)을 이미지로 잘라내어 `data/processed/cropped_components` 디렉터리에 저장.
    *   **변경:** `figure` 라벨은 `question_block`의 자식으로만 처리되며, 최상위 `figure`는 무시됩니다. `question_block`을 자를 때 `question_number`만 마스킹 처리하고, `figure` 자식 요소는 재조합 로직에서 별도로 처리하지 않습니다. (JSON에는 유지)
    *   `question_number`는 이미지로 자르지 않고 `question_block` 내에서 마스킹 처리.
    *   잘라낸 이미지들의 정보(label, image_path) 리스트를 논리적 단위로 그룹핑하여 반환하도록 기능 개선.
*   **논리적 단위 그룹핑 (`group_components_into_question_sets`):**
    *   잘라낸 구성 요소들을 `header`, `passage`와 그에 딸린 `question_block`들을 하나의 논리적인 "문제 세트"로 그룹핑하는 기능 구현.
    *   `footer`와 같은 독립적인 요소들은 별도의 논리적 단위로 처리.
*   **논리적 단위 셔플 (`shuffle_logical_units`):**
    *   그룹핑된 논리적 단위들 중에서 "문제 세트"에 해당하는 단위들만 무작위로 셔플하는 기능 구현.
    *   `header`, `footer`와 같은 고정된 요소들의 상대적 위치는 유지되도록 로직 개선.
    *   `footer`는 최종 재조합 리스트에서 제외되도록 수정.
*   **PDF 재조합 및 문제 번호 부여 (`recombine_pdf`):**
    *   잘라내고 셔플된 이미지 구성 요소들을 사용하여 새로운 PDF를 재조합하는 기능 구현.
    *   `question_block`에 새로운 문제 번호(1, 2, 3...)를 순차적으로 부여하는 기능 구현. (기존 `question_number` 이미지 위에 겹치지 않고 새로운 번호만 표시되도록 개선 완료)
    *   **개선:** 각 구성 요소를 배치하기 전에 페이지에 공간이 충분한지 개별적으로 확인하여, PDF가 중간에 잘리는 현상을 해결했습니다. `figure`는 `question_block` 내에 포함되어 처리되므로, 별도의 배치 문제가 발생하지 않습니다.
    *   **추가:** 설정 관리를 위해 `CONFIG` 딕셔너리를 도입했습니다.

## 3. 현재 상태 및 다음 단계

*   **현재 상태:** PDF에서 구획을 잘라내고, 지문-문제 세트를 그룹핑하여 셔플한 후, 새로운 문제 번호를 부여하여 PDF로 재조합하는 핵심 로직을 개발 중입니다.
*   **주요 해결된 문제:**
    *   PDF를 PNG로 변환 시 DPI 불일치로 인한 이미지 크롭 문제 해결.
    *   생성되는 이미지 파일명 중복 문제 해결 (원본 파일명 포함).
    *   PDF 재조합 시 이미지 크기 조절 및 B4 사이즈, 두 열 레이아웃 적용.
*   **현재 봉착한 문제:**
    *   **논리적 단위 그룹핑 및 순서 문제**: `header` - `passage` - `question_block` 간의 의미론적 계층 구조가 올바르게 유지되지 않고, `question_block`이 잘못된 `header-passage` 묶음에 할당되거나 순서가 뒤섞이는 문제 발생. (예: `header1 - questionbox1_1 - passage1 - questionbox1_2 - questionbox2_2 - questionbox2_1 - header2 - questionbox2_3`와 같은 비정상적인 순서).
    *   **이미지 크롭 기능 회귀**: 최근 코드 수정으로 인해 이미지 크롭 기능이 다시 제대로 작동하지 않는 문제 발생. (`_crop_and_create_component` 함수로의 `mask_bboxes` 전달 방식 오류로 추정).
*   **다음 단계:** `src/annotation_processor.py`의 논리적 단위 그룹핑 로직을 재검토하고, 이미지 크롭 기능의 회귀를 해결하는 데 집중할 예정입니다.