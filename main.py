# main.py  (página inicial)
from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime
import sqlite3
import streamlit as st

# ------------------ Config ------------------
st.set_page_config(page_title="Início", page_icon="🏠", layout="wide")
st.sidebar.title("Navegação")
st.sidebar.success("Selecione uma página acima.")

st.title("🏠 Início")
st.markdown("Bem-vindo ao painel principal do sistema de Lotes.")

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "dados.db"
BACKUPS_DIR = APP_DIR / "backups"

# ------------------ Helpers ------------------
def _connect():
    return sqlite3.connect(DB_PATH)

def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
    )
    return cur.fetchone() is not None

def _get_single_value(conn, sql: str, params: tuple = ()) -> int:
    try:
        row = conn.execute(sql, params).fetchone()
        return int(row[0] if row and row[0] is not None else 0)
    except Exception:
        return 0

def _fmt_bytes(n: int) -> str:
    for u in ["B","KB","MB","GB","TB"]:
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"

# ------------------ Consultas ------------------
duplicados_distintos = 0
duplicados_linhas = 0
total_lotes = pendentes = concluidos = 0
itens_em_lotes = 0
db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
ultimo_backup = None

with _connect() as conn:
    # 1) Duplicados de Lacre (na tabela 'animais')
    if _table_exists(conn, "animais"):
        # lacres distintos que aparecem mais de uma vez
        sql_groups = """
            SELECT COUNT(*) FROM (
              SELECT Lacre
              FROM animais
              WHERE Lacre IS NOT NULL AND TRIM(Lacre) <> ''
              GROUP BY Lacre
              HAVING COUNT(*) > 1
            ) x
        """
        duplicados_distintos = _get_single_value(conn, sql_groups)

        # total de linhas envolvidas nessas duplicidades (soma dos counts)
        sql_rows = """
            SELECT COALESCE(SUM(cnt),0) FROM (
              SELECT COUNT(*) AS cnt
              FROM animais
              WHERE Lacre IS NOT NULL AND TRIM(Lacre) <> ''
              GROUP BY Lacre
              HAVING COUNT(*) > 1
            ) t
        """
        duplicados_linhas = _get_single_value(conn, sql_rows)

    # 2) Métricas de lotes (se existirem)
    if _table_exists(conn, "lotes"):
        total_lotes = _get_single_value(conn, "SELECT COUNT(*) FROM lotes")
        pendentes = _get_single_value(conn, "SELECT COUNT(*) FROM lotes WHERE COALESCE(status,'pendente')='pendente'")
        concluidos = _get_single_value(conn, "SELECT COUNT(*) FROM lotes WHERE COALESCE(status,'pendente')='concluido'")

    # 3) Total de itens em lotes
    if _table_exists(conn, "lote_itens"):
        itens_em_lotes = _get_single_value(conn, "SELECT COUNT(*) FROM lote_itens")

# 4) Último backup local
if BACKUPS_DIR.exists():
    try:
        last = max(BACKUPS_DIR.glob("dados-*.sqlite"), key=lambda p: p.stat().st_mtime, default=None)
        if last:
            ultimo_backup = f"{last.name} — {datetime.fromtimestamp(last.stat().st_mtime):%d/%m/%Y %H:%M}"
    except ValueError:
        ultimo_backup = None

# ------------------ UI: Cards ------------------
# Pequeno CSS para “cardzinhos” simples
st.markdown("""
<style>
.card {
  border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px;
  background: #ffffff; box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.card h3 { font-size: 0.95rem; margin: 0 0 6px 0; color: #374151; }
.card .value { font-size: 2.0rem; font-weight: 700; line-height: 1.1; color: #111827; }
.card .sub { color: #6b7280; font-size: 0.9rem; margin-top: 4px; }
.card.warn { border-color: #f59e0b33; background: #fff7ed; }
.card.ok { border-color: #10b98133; background: #ecfdf5; }
</style>
""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns([1.2,1,1,1])

with c1:
    cls = "card warn" if duplicados_distintos > 0 else "card ok"
    st.markdown(
        f"""
        <div class="{cls}">
          <h3>🧩 Lacres duplicados (distintos)</h3>
          <div class="value">{duplicados_distintos}</div>
          <div class="sub">Linhas envolvidas: <b>{duplicados_linhas}</b></div>
        </div>
        """,
        unsafe_allow_html=True
    )
    # (opcional) mensagem discreta quando houver duplicados
    if duplicados_distintos > 0:
        st.caption("Use o atalho abaixo: **Duplicatas**.")
    else:
        st.caption("Nenhuma duplicata encontrada.")
        
with c2:
    st.markdown(
        f"""
        <div class="card">
          <h3>📦 Lotes (total)</h3>
          <div class="value">{total_lotes}</div>
          <div class="sub">Pendentes: <b>{pendentes}</b> • Concluídos: <b>{concluidos}</b></div>
        </div>
        """, unsafe_allow_html=True
    )

with c3:
    st.markdown(
        f"""
        <div class="card">
          <h3>📝 Itens em lotes</h3>
          <div class="value">{itens_em_lotes}</div>
          <div class="sub">Soma de registros em <code>lote_itens</code></div>
        </div>
        """, unsafe_allow_html=True
    )

with c4:
    lastbk = ultimo_backup or "—"
    st.markdown(
        f"""
        <div class="card">
          <h3>💾 Último backup</h3>
          <div class="value" style="font-size:1.2rem">{lastbk}</div>
          <div class="sub">Tamanho do DB: <b>{_fmt_bytes(db_size)}</b></div>
        </div>
        """, unsafe_allow_html=True
    )

st.divider()
st.markdown("### Atalhos rápidos")

# ordem: Duplicatas, Lote Pronto, Criar Lote, Backup
st.page_link("pages/6_Duplicatas.py", label="🧩 Duplicatas",   use_container_width=True)
st.page_link("pages/2_Lote_Pronto.py", label="📄 Lote Pronto", use_container_width=True)
st.page_link("pages/1_Criar_Lote.py",  label="🆕 Criar Lote",  use_container_width=True)
st.page_link("pages/5_Backup.py",      label="💾 Backup",      use_container_width=True)
