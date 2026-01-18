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

# --- Template Types ---
TPL_TYPE_ORDER = "order"
TPL_TYPE_INVOICE = "invoice"
TPL_TYPE_EXPORT = "export"
TPL_TYPE_BULK = "bulk"

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

TEMPLATE_TYPE_LABELS = {
    TPL_TYPE_ORDER: "Н?'Н1'Нs'бS, Н-`Н<?",
    TPL_TYPE_INVOICE: "ЙнoН   Н-`Н<?",
    TPL_TYPE_EXPORT: "ЙнoН   Й,'Й3'Й,'И,° Н-`Н<?",
    TPL_TYPE_BULK: "Н?мИ', Н-`Н<?",
}

TEMPLATE_TYPES_IN_ORDER = [TPL_TYPE_ORDER, TPL_TYPE_INVOICE, TPL_TYPE_EXPORT, TPL_TYPE_BULK]


# Mall Types: 없어도 될 듯 하다.
MALL_NAVER = "naver"
MALL_KAKAO = "kakao"
MALL_COUPANG = "coupang"


# --- Mapping Keys ---
MAP_ORDER_TO_INVOICE = "order_to_invoice"
MAP_BULK_MAPPING = "bulk_mapping"
MAP_BULK_MATCH = "bulk_match"

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

def get_bulk_mapping_fields(mapping_data=None):
    if mapping_data is None:
        all_mappings = st.session_state.get("mappings", {})
        mapping_records = all_mappings.get(MAP_BULK_MATCH, [])
        mapping_data = mapping_records[0]["rules"] if mapping_records else {}

    match_cols = mapping_data.get("match_columns", {})

    print("Target Mapping Data:", mapping_data)

    return [
        MappingField(
            "item", 
            match_cols.get("ecount_item", NOT_SELECTED), 
            match_cols.get("invoice_item", NOT_SELECTED)
        ),
        MappingField(
            "quantity", 
            match_cols.get("ecount_quantity", NOT_SELECTED), 
            match_cols.get("invoice_quantity", NOT_SELECTED)
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
