from collections import namedtuple
import streamlit as st

# Template types
TPL_TYPE_ORDER = "order"
TPL_TYPE_INVOICE = "invoice"
TPL_TYPE_EXPORT = "export"
TPL_TYPE_BULK = "bulk"

TEMPLATE_TYPE_LABELS = {
    TPL_TYPE_ORDER: "Order templates",
    TPL_TYPE_INVOICE: "Invoice template",
    TPL_TYPE_EXPORT: "Export template",
    TPL_TYPE_BULK: "Bulk upload templates",
}

TEMPLATE_SINGLE_TYPES = [TPL_TYPE_INVOICE, TPL_TYPE_EXPORT]
TEMPLATE_MULTI_TYPES = [TPL_TYPE_ORDER, TPL_TYPE_BULK]

# Mapping keys
MAP_ORDER_TO_INVOICE = "order_to_invoice"
MAP_BULK_MAPPING = "bulk_mapping"
MAP_BULK_MATCH = "bulk_match"

# UI texts
PAGE_TITLE = "excelConverter Final"
MAIN_TITLE = "excelConverter"

TAB_RUN = "Run"
TAB_SETUP = "Setup"

SETUP_TAB_TEMPLATES = "Templates"
SETUP_TAB_MAPPING_INVOICE = "Order -> Invoice mapping"
SETUP_TAB_MAPPING_BULK = "Bulk mapping"

# Default values
ROSEN_SHIPPING_COST = 2900
ROSEN_COST_TYPE = "\uc120\ubd88"  # 선불

# Special values
NOT_SELECTED = "(none)"
ROSEN_DELIVERY_FEE_COL = "\ubc30\uc1a1\ube44"  # 배송비
ROSEN_FEE_TYPE_COL = "\ubc30\uc1a1\uc720\ud615"  # 배송유형

# Default mapping rows
DEFAULT_MALL_RULES = [
    {"\ubab0\ucf54\ub4dc": "\ub124\uc774\ubc84", "\ucd9c\uace0\uc9c0\ucf54\ub4dc": "00001"},
    {"\ubab0\ucf54\ub4dc": "\uce74\uce74\uc624", "\ucd9c\uace0\uc9c0\ucf54\ub4dc": "00003"},
    {"\ubab0\ucf54\ub4dc": "\ucfe0\ud321", "\ucd9c\uace0\uc9c0\ucf54\ub4dc": "00004"},
]

MappingField = namedtuple("MappingField", ["id", "label_e", "label_i"])


def get_bulk_mapping_fields(mapping_data=None):
    if mapping_data is None:
        all_mappings = st.session_state.get("mappings", {})
        mapping_records = all_mappings.get(MAP_BULK_MATCH, [])
        mapping_data = mapping_records[0]["rules"] if mapping_records else {}

    match_cols = mapping_data.get("match_columns", {})

    return [
        MappingField("item", match_cols.get("ecount_item", NOT_SELECTED), match_cols.get("invoice_item", NOT_SELECTED)),
        MappingField("quantity", match_cols.get("ecount_quantity", NOT_SELECTED), match_cols.get("invoice_quantity", NOT_SELECTED)),
        MappingField("name", match_cols.get("ecount_name", NOT_SELECTED), match_cols.get("invoice_name", NOT_SELECTED)),
        MappingField("address", match_cols.get("ecount_address", NOT_SELECTED), match_cols.get("invoice_address", NOT_SELECTED)),
        MappingField("contact_mobile", match_cols.get("ecount_contact_mobile", NOT_SELECTED), match_cols.get("invoice_contact_mobile", NOT_SELECTED)),
        MappingField("msg", match_cols.get("ecount_msg", NOT_SELECTED), match_cols.get("invoice_msg", NOT_SELECTED)),
    ]
