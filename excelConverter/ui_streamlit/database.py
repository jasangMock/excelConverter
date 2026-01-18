import json
import os
import sqlite3
import streamlit as st

import constants as C

DB_NAME = "excel_converter.db"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, DB_NAME)

#db연결하여 반환?
def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
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
            source_template_id INTEGER NOT NULL,
            target_template_id INTEGER,
            rules_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(source_template_id) REFERENCES templates(id),
            FOREIGN KEY(target_template_id) REFERENCES templates(id)
        )
        """
    )


def _get_template_id(conn, template_type, template_name):
    if not template_type or not template_name:
        return None
    cur = conn.execute(
        "SELECT id FROM templates WHERE type = ? AND name = ?",
        (template_type, template_name),
    )
    row = cur.fetchone()
    return row[0] if row else None


def init_db():
    conn = get_db_conn()
    with conn:
        _ensure_schema(conn)
    conn.close()


def save_template(template_type, template_name, headers, header_row_idx):
    headers_json = json.dumps(headers, ensure_ascii=False)
    conn = get_db_conn()
    with conn:
        template_id = _get_template_id(conn, template_type, template_name)
        if template_id:
            conn.execute(
                """
                UPDATE templates
                SET headers_json = ?, header_row_idx = ?
                WHERE id = ?
                """,
                (headers_json, int(header_row_idx or 0), template_id),
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO templates (name, type, headers_json, header_row_idx)
                VALUES (?, ?, ?, ?)
                """,
                (template_name, template_type, headers_json, int(header_row_idx or 0)),
            )
            template_id = cur.lastrowid
    conn.close()
    st.toast(f"Saved template '{template_name}' ({template_type}).")
    return template_id


def save_mapping(mapping_type, source_template_id, target_template_id, rules_dict):
    rules_json = json.dumps(rules_dict, ensure_ascii=False)
    conn = get_db_conn()
    with conn:
        cur = conn.execute(
            """
            SELECT id FROM mappings
            WHERE mapping_type = ? AND source_template_id IS ? AND target_template_id IS ?
            """,
            (mapping_type, source_template_id, target_template_id),
        )
        row = cur.fetchone()
        if row:
            conn.execute(
                """
                UPDATE mappings
                SET rules_json = ?
                WHERE id = ?
                """,
                (rules_json, row["id"]),
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO mappings (mapping_type, source_template_id, target_template_id, rules_json)
                VALUES (?, ?, ?, ?)
                """,
                (mapping_type, source_template_id, target_template_id, rules_json),
            )
            row = {"id": cur.lastrowid}
    conn.close()
    st.toast("Saved mapping.")
    return row["id"] if row else None


def load_all_config_from_db():
    conn = get_db_conn()
    templates_by_type = {}
    mappings_by_type = {}

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
            templates_by_type.setdefault(row["type"], {})[row["name"]] = template

        cur = conn.execute("SELECT * FROM mappings")
        for row in cur.fetchall():
            try:
                rules = json.loads(row["rules_json"])
            except json.JSONDecodeError:
                st.error(f"DB: mapping decode failed for id={row['id']}")
                rules = {}

            mapping = {
                "id": row["id"],
                "mapping_type": row["mapping_type"],
                "source_template_id": row["source_template_id"],
                "target_template_id": row["target_template_id"],
                "rules": rules,
            }
            mappings_by_type.setdefault(row["mapping_type"], []).append(mapping)

    conn.close()
    return templates_by_type, mappings_by_type


def delete_template(template_id):
    conn = get_db_conn()
    try:
        with conn:
            conn.execute(
                "DELETE FROM mappings WHERE source_template_id = ? OR target_template_id = ?",
                (template_id, template_id),
            )
            cur = conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        if cur.rowcount > 0:
            st.toast("Template deleted.")
    finally:
        conn.close()
