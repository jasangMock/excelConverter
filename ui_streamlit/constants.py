from collections import namedtuple
import streamlit as st

# --- Template Keys ---
TPL_ECOUNT = "ecount"
TPL_ROSEN = "rosen"
TPL_NAVER = "naver"
TPL_KAKAO = "kakao"
TPL_COUPANG = "coupang"
TPL_ROSEN_INVOICE = "rosen_invoice"
TPL_ECOUNT_BULK = "ecount_bulk"

# --- Template Labels ---
TEMPLATE_LABELS = {
    TPL_ECOUNT: "이카운트 주문서",
    TPL_ROSEN: "로젠 송장 양식 (변환용)",
    TPL_NAVER: "네이버 스마트스토어 양식",
    TPL_KAKAO: "카카오 선물하기 양식",
    TPL_COUPANG: "쿠팡 양식",
    TPL_ROSEN_INVOICE: "로젠 내보내기 양식 (송장번호 포함)",
    TPL_ECOUNT_BULK: "이카운트 일괄 양식 (최종 결과물)"
}

TEMPLATE_KEYS_IN_ORDER = [TPL_ECOUNT, TPL_ROSEN, TPL_NAVER, TPL_KAKAO, TPL_COUPANG,TPL_ROSEN_INVOICE, TPL_ECOUNT_BULK]


# Mall Types
MALL_NAVER = "naver"
MALL_KAKAO = "kakao"
MALL_COUPANG = "coupang"


# --- Mapping Keys ---
MAP_ECOUNT_TO_ROSEN = "ecount_to_rosen"
MAP_BULK_ECOUNT = "bulk_ecount"
MAP_NAVER_TO_ROSEN = "naver_to_rosen"
MAP_KAKAO_TO_ROSEN = "kakao_to_rosen"
MAP_COUPANG_TO_ROSEN = "coupang_to_rosen"

# --- UI Texts ---
PAGE_TITLE = "excelConverter Final"
MAIN_TITLE = "🚚 excelConverter (Final)"

TAB_RUN = "실행 (매일 작업)"
TAB_SETUP = "설정 (최초 1회)"

SETUP_TAB1_TITLE = "1. 양식 등록"
SETUP_TAB2_TITLE = "2. 이카운트 -> 로젠 변환 매핑"
SETUP_TAB3_TITLE = "3. 네이버 -> 로젠 변환 매핑"
SETUP_TAB4_TITLE = "4. 일괄 양식 매칭 설정"

# --- Default Values ---
ROSEN_SHIPPING_COST = 2900
ROSEN_COST_TYPE = "신용"

# --- Special Values ---
NOT_SELECTED = "(선택 안 함)"
ROSEN_DELIVERY_FEE_COL = "택배운임"
ROSEN_FEE_TYPE_COL = "운임구분"



# 기본 쇼핑몰 변환 규칙 예시
DEFAULT_MALL_RULES = [
    {"수집처명": "네이버스마트스토어", "쇼핑몰코드": "00001"},
    {"수집처명": "카카오 선물하기", "쇼핑몰코드": "00003"},
    {"수집처명": "쿠팡", "쇼핑몰코드": "00004"},
]

# 1. 데이터 구조 정의 (설계도)
# id: 내부 식별자 (예: item)
# label_e: 이카운트 쪽 표시 라벨
# label_i: 로젠 쪽 표시 라벨
MappingField = namedtuple("MappingField", ["id", "label_e", "label_i"])

def get_bulk_mapping_fields():
# 1. 'mappings' 세션 키가 있는지 먼저 확인
    all_mappings = st.session_state.get('mappings', {})
    
    # 2. 그 안에서 'bulk_ecount' 데이터를 꺼냄 (MAP_BULK_ECOUNT == "bulk_ecount")
    mapping_data = all_mappings.get(MAP_BULK_ECOUNT, {})
    
    # 3. 그 안에서 다시 'match_columns'를 꺼냄
    match_cols = mapping_data.get("match_columns", {})

    print("Target Mapping Data:", mapping_data) # 이제 데이터가 출력될 것입니다.

    # 2. MappingField 리스트를 동적으로 생성합니다.
    # key 값이 없을 경우를 대비해 기본값(NOT_SELECTED)을 설정합니다.
    return [
        MappingField(
            "item", 
            match_cols.get("ecount_item", NOT_SELECTED), 
            match_cols.get("invoice_item", NOT_SELECTED)
        ),
        MappingField(
            "quantity", 
            match_cols.get("ecount_quantity", NOT_SELECTED), 
            match_cols.get("invoice_quantity", NOT_SELECTED) # JSON의 오타(invoie) 주의
        ),
        MappingField(
            "name", 
            match_cols.get("ecount_name", NOT_SELECTED), 
            match_cols.get("invoice_name", NOT_SELECTED)
        ),
        MappingField(
            "address", 
            match_cols.get("ecount_address", NOT_SELECTED), 
            match_cols.get("invoice_address", NOT_SELECTED)
        ),
        MappingField(
            "contact_mobile", 
            match_cols.get("ecount_contact_mobile", NOT_SELECTED), 
            match_cols.get("invoice_contact_mobile", NOT_SELECTED)
        ),
        MappingField(
            "msg", 
            match_cols.get("ecount_msg", NOT_SELECTED), 
            match_cols.get("invoice_msg", NOT_SELECTED)
        ),
    ]