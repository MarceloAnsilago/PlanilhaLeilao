# pages/8_Animais_Fora.py
from __future__ import annotations
from pathlib import Path
import sqlite3
import csv
import io
import streamlit as st

st.set_page_config(page_title="Animais fora de lote", page_icon="🐮", layout="wide")
st.title("🐮 Animais fora de lote")
st.caption("Registros da tabela `animais` que não possuem vínculo em `lote_itens`.")

APP_DIR = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path(".")
DB_PATH = APP_DIR / "dados.db"

# ---------------- Helpers ----------------
def _connect():
    return sqlite3.connect(DB_PATH)

def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,))
    return cur.fetchone() is not None

def _colnames(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]

def _pick_existing(candidates: list[str], existing: set[str]) -> str | None:
    """Retorna o primeiro nome de coluna que existir (case-sensitive como no SQLite)."""
    for c in candidates:
        if c in existing:
            return c
    return None

# ---------------- Detecção de colunas ----------------
with _connect() as conn:
    if not _table_exists(conn, "animais"):
        st.error("Tabela `animais` não encontrada.")
        st.stop()

    cols = set(_colnames(conn, "animais"))

serie_col = _pick_existing(['N.º Série', 'Nº Série', 'Numero Série', 'N_Serie', 'Serie', 'Série'], cols) or 'rowid'
lacre_col = _pick_existing(['Lacre', 'LACRE', 'lacre'], cols) or 'Lacre'
prop_col  = _pick_existing(['Proprietário Origem', 'Proprietario Origem', 'Proprietário', 'Proprietario', 'Origem'], cols) or 'Proprietário Origem'

# ---------------- Busca ----------------
q = st.text_input("🔎 Buscar por Série / Lacre / Proprietário", "", placeholder="ex.: 123, ABC..., João...")

# ---------------- Query ----------------
rows = []
total = 0
with _connect() as conn:
    has_lote_itens = _table_exists(conn, "lote_itens")
    if not has_lote_itens:
        st.warning("Tabela `lote_itens` não existe. Considerando que todos os animais estão fora de lote.")
        sql = f'SELECT "{serie_col}" as serie, "{lacre_col}" as lacre, "{prop_col}" as proprietario FROM animais'
        rows = conn.execute(sql).fetchall()
    else:
        sql = f"""
            SELECT a."{serie_col}" as serie,
                   a."{lacre_col}" as lacre,
                   a."{prop_col}"  as proprietario
            FROM animais a
            WHERE NOT EXISTS (
              SELECT 1 FROM lote_itens li
              WHERE li.animal_rowid = a.rowid
            )
        """
        rows = conn.execute(sql).fetchall()

# filtro em memória
def _match(row: tuple[str,str,str], term: str) -> bool:
    term = term.strip().lower()
    if not term:
        return True
    return any((str(x or "").lower().find(term) >= 0) for x in row)

filtered = [r for r in rows if _match(r, q)]
total = len(filtered)

# ---------------- UI ----------------
st.write(f"**Total encontrados:** {total}")

# Baixar CSV
if filtered:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Série", "Lacre", "Proprietário Origem"])
    for r in filtered:
        writer.writerow(list(r))
    csv_bytes = buf.getvalue().encode("utf-8-sig")
    st.download_button("⬇️ Baixar CSV", data=csv_bytes, file_name="animais_fora_de_lote.csv", use_container_width=True)

# Dataframe
if filtered:
    # Streamlit aceita lista de dicts
    data = [{"Série": r[0], "Lacre": r[1], "Proprietário Origem": r[2]} for r in filtered]
    st.dataframe(data, use_container_width=True, hide_index=True)
else:
    st.info("Nenhum registro fora de lote para os filtros atuais.")
