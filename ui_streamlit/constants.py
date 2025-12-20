from collections import namedtuple

# 1. 데이터 구조 정의 (설계도)
# id: 내부 식별자 (예: item)
# label_e: 이카운트 쪽 표시 라벨
# label_i: 로젠 쪽 표시 라벨
MappingField = namedtuple("MappingField", ["id", "label_e", "label_i"])

# 2. 데이터 정의 (순수 정보만 남김 -> 가독성 극대화)
BULK_MAPPING_FIELDS = [
    MappingField("item",           "쇼핑몰상품명 컬럼",        "품목명 컬럼"),
    MappingField("quantity",       "수량 컬럼",                "박스수량 컬럼"),
    MappingField("name",           "수취인 컬럼",              "수하인명 컬럼"),
    MappingField("address",        "주소 컬럼",                "수하인주소 컬럼"),
    MappingField("contact_mobile", "수취인 연락처1 (휴대폰)",  "수하인핸드폰번호 컬럼"),
    MappingField("msg",            "배송요청사항 컬럼",        "배송메세지 컬럼"),
]

# --- Template Keys ---
TPL_ECOUNT = "ecount"
TPL_ROSEN = "rosen"
TPL_ROSEN_INVOICE = "rosen_invoice"
TPL_ECOUNT_BULK = "ecount_bulk"

# --- Template Labels ---
TEMPLATE_LABELS = {
    TPL_ECOUNT: "이카운트 주문서",
    TPL_ROSEN: "로젠 송장 양식 (변환용)",
    TPL_ROSEN_INVOICE: "로젠 내보내기 양식 (송장번호 포함)",
    TPL_ECOUNT_BULK: "이카운트 일괄 양식 (최종 결과물)"
}

TEMPLATE_KEYS_IN_ORDER = [TPL_ECOUNT, TPL_ROSEN, TPL_ROSEN_INVOICE, TPL_ECOUNT_BULK]

# --- Mapping Keys ---
MAP_ECOUNT_TO_ROSEN = "ecount_to_rosen"
MAP_BULK_ECOUNT = "bulk_ecount"

# --- UI Texts ---
PAGE_TITLE = "excelConverter Final"
MAIN_TITLE = "🚚 excelConverter (Final)"

TAB_RUN = "실행 (매일 작업)"
TAB_SETUP = "설정 (최초 1회)"

SETUP_TAB1_TITLE = "1. 양식 등록"
SETUP_TAB2_TITLE = "2. 로젠 변환 매핑"
SETUP_TAB3_TITLE = "3. 일괄 양식 매칭 설정"

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

