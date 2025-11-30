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