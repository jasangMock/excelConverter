import io
import pandas as pd
import streamlit as st
import msoffcrypto
from xlrd import XLRDError

TARGET_KEYWORDS = ["\uc218\ucde8\uc778", "\ud0dd\ubc30\uc0ac", "\uc0c1\ud488\uba85", "\uc8fc\ubb38\uc790"]


def load_data_v2(uploaded_file, is_merged=False):
    if uploaded_file is None:
        return None
    try:
        raw_df = pd.read_excel(uploaded_file, header=None)
        header_row_idx = 0
        for idx, row in raw_df.iterrows():
            row_str = " ".join(row.astype(str))
            if any(key in row_str for key in TARGET_KEYWORDS):
                header_row_idx = idx
                break
        st.info(f"Detected header row: {header_row_idx + 1}")

        if is_merged:
            header_part = raw_df.iloc[header_row_idx: header_row_idx + 2]
            new_cols = []
            for i in range(len(raw_df.columns)):
                top = str(header_part.iloc[0, i]).replace('\\n', '').strip() if pd.notna(header_part.iloc[0, i]) else ""
                bot = str(header_part.iloc[1, i]).replace('\\n', '').strip() if pd.notna(header_part.iloc[1, i]) else ""
                top = "" if "Unnamed" in top or top == "nan" else top
                bot = "" if "Unnamed" in bot or bot == "nan" else bot
                if top == bot or not bot:
                    new_cols.append(top if top else f"Col_{i}")
                elif not top:
                    new_cols.append(bot)
                else:
                    new_cols.append(f"{top}_{bot}")
            df = raw_df.iloc[header_row_idx + 2:].copy()
            df.columns = new_cols
        else:
            df = raw_df.iloc[header_row_idx + 1:].copy()
            df.columns = raw_df.iloc[header_row_idx]

        return df.dropna(how='all').reset_index(drop=True)
    except Exception as e:
        st.error(f"Failed to read file: {e}")
        return None


def load_data(uploaded_file, header_row_idx=0):
    if uploaded_file is None:
        return None
    try:
        if uploaded_file.name.lower().endswith('.csv'):
            try:
                return pd.read_csv(uploaded_file, encoding='cp949', header=header_row_idx)
            except Exception:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, encoding='utf-8-sig', header=header_row_idx)
        return pd.read_excel(uploaded_file, header=header_row_idx)
    except Exception as e:
        st.error(f"Failed to read file: {e}")
        return None


def to_excel_bytes(df):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    bio.seek(0)
    return bio.getvalue()


def clean_text(text):
    return str(text).replace(" ", "").strip()


def clean_qty(val):
    try:
        return str(int(float(val)))
    except Exception:
        return str(val)


def load_headers(uploaded_file, header_row_idx=0, password=None):
    if uploaded_file is None:
        return None
    try:
        uploaded_file.seek(0)
        if uploaded_file.name.lower().endswith('.csv'):
            df = pd.read_csv(uploaded_file, encoding='cp949', header=header_row_idx, nrows=0)
        else:
            target_file = uploaded_file
            if password:
                try:
                    decrypted_workbook = io.BytesIO()
                    office_file = msoffcrypto.OfficeFile(uploaded_file)
                    office_file.load_key(password=password)
                    office_file.decrypt(decrypted_workbook)
                    decrypted_workbook.seek(0)
                    target_file = decrypted_workbook
                except Exception:
                    st.error("Incorrect password.")
                    return None
            df = pd.read_excel(target_file, header=header_row_idx, nrows=0)
        raw_columns = list(df.columns)
        processed_columns = ["" if str(col).startswith("Unnamed:") else str(col) for col in raw_columns]
        return processed_columns
    except XLRDError as e:
        if "encrypted" in str(e):
            st.warning("Encrypted file. Please provide a password.")
            return None
        raise e
    except Exception as e:
        st.error(f"Failed to read headers: {e}")
        return None


def load_data_merged_header(uploaded_file, start_row_idx=1):
    try:
        df = pd.read_excel(uploaded_file, header=[start_row_idx, start_row_idx + 1])
        new_columns = []
        for col in df.columns:
            top_level = str(col[0]).replace('\\n', '').strip() if pd.notna(col[0]) else ""
            bottom_level = str(col[1]).replace('\\n', '').strip() if pd.notna(col[1]) else ""
            if top_level == bottom_level:
                new_columns.append(top_level)
            elif "Unnamed" in bottom_level or bottom_level == "nan" or bottom_level == "":
                new_columns.append(top_level)
            elif "Unnamed" in top_level or top_level == "nan" or top_level == "":
                new_columns.append(bottom_level)
            else:
                new_columns.append(f"{top_level}_{bottom_level}")
        df.columns = new_columns
        return df
    except Exception as e:
        print(f"Error merging headers: {e}")
        return None


def rules_to_dataframe(rules_dict, default_list):
    if rules_dict:
        data = [{"\ubab0\ucf54\ub4dc": k, "\ucd9c\uace0\uc9c0\ucf54\ub4dc": v} for k, v in rules_dict.items()]
    else:
        data = default_list
    return pd.DataFrame(data)


def dataframe_to_rules(df):
    rule_dict = {}
    for _, row in df.iterrows():
        key = str(row["\ubab0\ucf54\ub4dc"]).strip()
        val = str(row["\ucd9c\uace0\uc9c0\ucf54\ub4dc"]).strip()
        if key and val and key.lower() != "none" and val.lower() != "none":
            rule_dict[key] = val
    return rule_dict


def reset_conversion():
    if "conversion_result" in st.session_state:
        del st.session_state.conversion_result


def find_first_existing_col(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None


def clean_numeric_series(series):
    return (
        series.astype(str)
        .str.replace(r'\\.0$', '', regex=True)
        .replace(['nan', 'None', 'NaN'], '')
    )
