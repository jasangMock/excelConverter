import json
import os
import sqlite3
import streamlit as st

DB_NAME = "excel_converter.db"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, DB_NAME)


def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL,
            headers_json TEXT NOT NULL,
            header_row_idx INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mapping_type TEXT NOT NULL,
            target_template_id INTEGER NOT NULL,
            rules_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(target_template_id) REFERENCES templates(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mapping_sources (
            mapping_id INTEGER NOT NULL,
            source_template_id INTEGER NOT NULL,
            source_order INTEGER DEFAULT 0,
            PRIMARY KEY (mapping_id, source_template_id),
            FOREIGN KEY(mapping_id) REFERENCES mappings(id),
            FOREIGN KEY(source_template_id) REFERENCES templates(id)
        )
        """
    )


def _get_template_id_by_name(conn, template_name):
    if not template_name:
        return None
    cur = conn.execute(
        "SELECT id FROM templates WHERE name = ?",
        (template_name,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def init_db():
    conn = get_db_conn()
    with conn:
        _ensure_schema(conn)
    conn.close()


def save_template(name, template_type, headers, header_row_idx):
    headers_json = json.dumps(headers, ensure_ascii=False)
    conn = get_db_conn()
    with conn:
        template_id = _get_template_id_by_name(conn, name)
        if template_id:
            conn.execute(
                """
                UPDATE templates
                SET type = ?, headers_json = ?, header_row_idx = ?
                WHERE id = ?
                """,
                (template_type, headers_json, int(header_row_idx or 0), template_id),
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO templates (name, type, headers_json, header_row_idx)
                VALUES (?, ?, ?, ?)
                """,
                (name, template_type, headers_json, int(header_row_idx or 0)),
            )
            template_id = cur.lastrowid
    conn.close()
    st.toast(f"Saved template '{name}' ({template_type}).")
    return template_id


def _find_mapping_id(conn, mapping_type, target_template_id, source_template_ids):
    """Find mapping id that matches mapping_type/target and exact source set."""
    source_set = set(source_template_ids or [])
    cur = conn.execute(
        "SELECT id FROM mappings WHERE mapping_type = ? AND target_template_id = ?",
        (mapping_type, target_template_id),
    )
    for row in cur.fetchall():
        mid = row[0]
        src_rows = conn.execute(
            "SELECT source_template_id FROM mapping_sources WHERE mapping_id = ?",
            (mid,),
        ).fetchall()
        existing_set = {r[0] for r in src_rows}
        if existing_set == source_set:
            return mid
    return None


def save_mapping(mapping_type, target_template_id, source_template_ids, rules_dict):
    rules_json = json.dumps(rules_dict or {}, ensure_ascii=False)
    conn = get_db_conn()
    with conn:
        source_ids = list(dict.fromkeys(source_template_ids or []))
        mapping_id = _find_mapping_id(conn, mapping_type, target_template_id, source_ids)

        if mapping_id:
            conn.execute(
                "UPDATE mappings SET rules_json = ? WHERE id = ?",
                (rules_json, mapping_id),
            )
            conn.execute("DELETE FROM mapping_sources WHERE mapping_id = ?", (mapping_id,))
        else:
            cur = conn.execute(
                """
                INSERT INTO mappings (mapping_type, target_template_id, rules_json)
                VALUES (?, ?, ?)
                """,
                (mapping_type, target_template_id, rules_json),
            )
            mapping_id = cur.lastrowid

        for order, sid in enumerate(source_ids):
            conn.execute(
                """
                INSERT OR REPLACE INTO mapping_sources (mapping_id, source_template_id, source_order)
                VALUES (?, ?, ?)
                """,
                (mapping_id, sid, order),
            )
    conn.close()
    st.toast("Saved mapping.")
    return mapping_id


def load_templates():
    conn = get_db_conn()
    templates_by_type = {}
    with conn:
        cur = conn.execute("SELECT * FROM templates")
        for row in cur.fetchall():
            try:
                headers = json.loads(row["headers_json"])
            except json.JSONDecodeError:
                st.error(f"DB: template decode failed for id={row['id']}")
                headers = []

            template = {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "headers": headers,
                "header_row_idx": row["header_row_idx"],
            }
            templates_by_type.setdefault(row["type"], []).append(template)
    conn.close()
    return templates_by_type


def load_mappings():
    conn = get_db_conn()
    mappings_by_type = {}
    with conn:
        cur = conn.execute("SELECT * FROM mappings")
        mapping_rows = cur.fetchall()
        for row in mapping_rows:
            try:
                rules = json.loads(row["rules_json"])
            except json.JSONDecodeError:
                st.error(f"DB: mapping decode failed for id={row['id']}")
                rules = {}

            src_cur = conn.execute(
                "SELECT source_template_id FROM mapping_sources WHERE mapping_id = ? ORDER BY source_order, source_template_id",
                (row["id"],),
            ) #mapping_sources 테이블에서 하나의 매핑에 대해 묶인 여러 탬플릿들을 가져온다. 
            sources = [r[0] for r in src_cur.fetchall()]

            mapping = {
                "id": row["id"],
                "mapping_type": row["mapping_type"],
                "target_template_id": row["target_template_id"],
                "rules": rules,
                "sources": sources,
            }
            mappings_by_type.setdefault(row["mapping_type"], []).append(mapping)
    conn.close()
    return mappings_by_type


def delete_template(template_id):
    conn = get_db_conn()
    try:
        with conn:
            # collect related mappings
            rows = conn.execute(
                """
                SELECT id FROM mappings WHERE target_template_id = ?
                UNION
                SELECT mapping_id AS id FROM mapping_sources WHERE source_template_id = ?
                """,
                (template_id, template_id),
            ).fetchall()
            mapping_ids = [r[0] for r in rows]
            if mapping_ids:
                conn.execute(
                    f"DELETE FROM mapping_sources WHERE mapping_id IN ({','.join('?'*len(mapping_ids))})",
                    mapping_ids,
                )
                conn.execute(
                    f"DELETE FROM mappings WHERE id IN ({','.join('?'*len(mapping_ids))})",
                    mapping_ids,
                )
            conn.execute("DELETE FROM mapping_sources WHERE source_template_id = ?", (template_id,))
            cur = conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        if cur.rowcount > 0:
            st.toast("Template deleted.")
    finally:
        conn.close()
