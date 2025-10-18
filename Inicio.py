# main.py  (página inicial)
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import sqlite3
import streamlit as st

# ------------------ Config ------------------
st.set_page_config(page_title="Início", page_icon="🏠", layout="wide")
st.title("🏠 Início")
st.sidebar.success("Selecione uma página acima.")

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

def _get_single_value(conn, sql: str, params: tuple = ()) -> int | float:
    try:
        row = conn.execute(sql, params).fetchone()
        return float(row[0] if row and row[0] is not None else 0)
    except Exception:
        return 0

def _fmt_bytes(n: int) -> str:
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"

def _colnames(conn, table: str) -> list[str]:
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    except Exception:
        return []

# ------------------ Consultas ------------------
duplicados_distintos = duplicados_linhas = 0
total_lotes = pendentes = concluidos = 0
itens_em_lotes = total_animais = 0
animais_em_lote = animais_sem_lacre = animais_sem_lote = 0
lacres_distintos = proprietarios_distintos = 0
lotes_com_itens = lotes_vazios = 0
media_itens_por_lote = 0.0
qtd_m = qtd_f = 0
total_individuos = 0
db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
ultimo_backup = None

with _connect() as conn:
    # 1) Duplicados / animais
    if _table_exists(conn, "animais"):
        cols_animais = set(_colnames(conn, "animais"))

        duplicados_distintos = _get_single_value(conn, """
            SELECT COUNT(*) FROM (
              SELECT Lacre FROM animais
              WHERE Lacre IS NOT NULL AND TRIM(Lacre) <> ''
              GROUP BY Lacre HAVING COUNT(*) > 1
            ) x
        """)
        duplicados_linhas = _get_single_value(conn, """
            SELECT COALESCE(SUM(cnt),0) FROM (
              SELECT COUNT(*) AS cnt FROM animais
              WHERE Lacre IS NOT NULL AND TRIM(Lacre) <> ''
              GROUP BY Lacre HAVING COUNT(*) > 1
            ) t
        """)
        total_animais = _get_single_value(conn, "SELECT COUNT(*) FROM animais")

        if _table_exists(conn, "lote_itens"):
            animais_em_lote = _get_single_value(conn, """
                SELECT COUNT(DISTINCT li.animal_rowid)
                FROM lote_itens li
                JOIN animais a ON a.rowid = li.animal_rowid
            """)
            animais_sem_lote = _get_single_value(conn, """
                SELECT COUNT(*) FROM animais a
                WHERE NOT EXISTS (
                  SELECT 1 FROM lote_itens li WHERE li.animal_rowid = a.rowid
                )
            """)
        else:
            animais_sem_lote = total_animais

        animais_sem_lacre = _get_single_value(conn, """
            SELECT COUNT(*) FROM animais
            WHERE Lacre IS NULL OR TRIM(Lacre) = ''
        """)
        lacres_distintos = _get_single_value(conn, """
            SELECT COUNT(DISTINCT Lacre) FROM animais
            WHERE Lacre IS NOT NULL AND TRIM(Lacre) <> ''
        """)
        proprietarios_distintos = _get_single_value(conn, """
            SELECT COUNT(DISTINCT "Proprietário Origem") FROM animais
        """)

        # ---- Sexo: somar colunas "Total M" / "Total F" ----
        if "Total M" in cols_animais:
            qtd_m = _get_single_value(conn, 'SELECT COALESCE(SUM("Total M"),0) FROM animais')
        if "Total F" in cols_animais:
            qtd_f = _get_single_value(conn, 'SELECT COALESCE(SUM("Total F"),0) FROM animais')

        # ---- Indivíduos: somar "Total Animais" (se existir) ----
        if "Total Animais" in cols_animais:
            total_individuos = _get_single_value(conn, 'SELECT COALESCE(SUM("Total Animais"),0) FROM animais')

    # 2) Lotes
    if _table_exists(conn, "lotes"):
        total_lotes = _get_single_value(conn, "SELECT COUNT(*) FROM lotes")
        pendentes = _get_single_value(conn, "SELECT COUNT(*) FROM lotes WHERE COALESCE(status,'pendente')='pendente'")
        concluidos = _get_single_value(conn, "SELECT COUNT(*) FROM lotes WHERE COALESCE(status,'pendente')='concluido'")

    # 3) Itens em lotes
    if _table_exists(conn, "lote_itens"):
        itens_em_lotes = _get_single_value(conn, "SELECT COUNT(*) FROM lote_itens")
        lotes_com_itens = _get_single_value(conn, """
            SELECT COUNT(*) FROM (
              SELECT lote_numero FROM lote_itens GROUP BY lote_numero HAVING COUNT(*)>0
            )
        """)
        lotes_vazios = max(int(total_lotes) - int(lotes_com_itens), 0)
        media_itens_por_lote = _get_single_value(conn, """
            SELECT AVG(c*1.0) FROM (
              SELECT COUNT(*) c FROM lote_itens GROUP BY lote_numero
            )
        """)

# 4) Último backup
if BACKUPS_DIR.exists():
    try:
        last = max(BACKUPS_DIR.glob("dados-*.sqlite"), key=lambda p: p.stat().st_mtime, default=None)
        if last:
            ultimo_backup = f"{last.name} — {datetime.fromtimestamp(last.stat().st_mtime):%d/%m/%Y %H:%M}"
    except ValueError:
        ultimo_backup = None

# ------------------ UI: Cards ------------------
st.markdown("""
<style>
.card {
  border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px;
  background: #ffffff; box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  height: 140px; display:flex; flex-direction:column; justify-content:space-between;
}
.card h3 { font-size: 0.95rem; margin: 0 0 6px 0; color: #374151; }
.card .value { font-size: 2.0rem; font-weight: 700; line-height: 1.1; color: #111827; }
.card .sub { color: #6b7280; font-size: 0.9rem; margin-top: 4px; }
.card.warn { border-color: #f59e0b33; background: #fff7ed; }
.card.ok { border-color: #10b98133; background: #ecfdf5; }
.k { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:.9rem; padding:.1rem .25rem; background:#f3f4f6; border-radius:6px; }
</style>
""", unsafe_allow_html=True)

# ---- Primeira linha ----
c1, c2, c3, c4 = st.columns([1.2,1,1,1])
with c1:
    cls = "card warn" if int(duplicados_distintos) > 0 else "card ok"
    st.markdown(
        f"""
        <div class="{cls}">
          <h3>🧩 Lacres duplicados (distintos)</h3>
          <div class="value">{int(duplicados_distintos)}</div>
          <div class="sub">Linhas envolvidas: <b>{int(duplicados_linhas)}</b></div>
        </div>
        """, unsafe_allow_html=True)
    st.caption("Use o atalho abaixo: **Duplicatas**." if duplicados_distintos else "Nenhuma duplicata encontrada.")

with c2:
    st.markdown(f"""
        <div class="card">
          <h3>📦 Lotes (total)</h3>
          <div class="value">{int(total_lotes)}</div>
          <div class="sub">Pendentes: <b>{int(pendentes)}</b> • Concluídos: <b>{int(concluidos)}</b></div>
        </div>""", unsafe_allow_html=True)

with c3:
    st.markdown(f"""
        <div class="card">
          <h3>📋 Itens em lotes</h3>
          <div class="value">{int(itens_em_lotes)}</div>
          <div class="sub">Soma de registros em <span class="k">lote_itens</span></div>
        </div>""", unsafe_allow_html=True)

with c4:
    st.markdown(f"""
        <div class="card">
          <h3>💾 Último backup</h3>
          <div class="value" style="font-size:1.1rem">{ultimo_backup or "—"}</div>
          <div class="sub">Tamanho do DB: <b>{_fmt_bytes(int(db_size))}</b></div>
        </div>""", unsafe_allow_html=True)

# ---- Segunda linha ----
r1, r2, r3, r4 = st.columns(4)
with r1:
    st.markdown(f"""
        <div class="card">
          <h3>🧮 Número de linhas</h3>
          <div class="value">{int(total_animais)}</div>
          <div class="sub">Linhas na tabela <span class="k">animais</span></div>
        </div>""", unsafe_allow_html=True)

with r2:
    st.markdown(f"""
        <div class="card">
          <h3>🐮 Animais fora de lotes</h3>
          <div class="value">{int(animais_sem_lote)}</div>
          <div class="sub">Sem vínculo em <span class="k">lote_itens</span></div>
        </div>""", unsafe_allow_html=True)

with r3:
    st.markdown(f"""
        <div class="card">
          <h3>📦→🐄 Animais em lotes</h3>
          <div class="value">{int(animais_em_lote)}</div>
          <div class="sub">Com vínculo em <span class="k">lote_itens</span></div>
        </div>""", unsafe_allow_html=True)

with r4:
    pct = (animais_em_lote / total_animais * 100) if total_animais else 0
    st.markdown(f"""
        <div class="card">
          <h3>📈 Cobertura</h3>
          <div class="value">{pct:.0f}%</div>
          <div class="sub">% de animais já associados</div>
        </div>""", unsafe_allow_html=True)

# ---- Terceira linha ----
s1, s2, s3, s4 = st.columns(4)
with s1:
    st.markdown(f"""
        <div class="card">
          <h3>🏷️ Lacres distintos</h3>
          <div class="value">{int(lacres_distintos)}</div>
          <div class="sub">Valores únicos válidos</div>
        </div>""", unsafe_allow_html=True)

with s2:
    st.markdown(f"""
        <div class="card">
          <h3>🚫 Animais sem lacre</h3>
          <div class="value">{int(animais_sem_lacre)}</div>
          <div class="sub"><span class="k">Lacre</span> vazio/nulo</div>
        </div>""", unsafe_allow_html=True)

with s3:
    st.markdown(f"""
        <div class="card">
          <h3>👤 Proprietários distintos</h3>
          <div class="value">{int(proprietarios_distintos)}</div>
          <div class="sub">Em <span class="k">Proprietário Origem</span></div>
        </div>""", unsafe_allow_html=True)

with s4:
    st.markdown(f"""
        <div class="card">
          <h3>📦 Lotes com itens / vazios</h3>
          <div class="value">{int(lotes_com_itens)} / {int(lotes_vazios)}</div>
          <div class="sub">Média itens/lote: <b>{float(media_itens_por_lote):.1f}</b></div>
        </div>""", unsafe_allow_html=True)

# ---- Quarta linha ----
t1, t2, t3, _ = st.columns(4)
with t1:
    st.markdown(f"""
        <div class="card">
          <h3>♂️ Machos (indivíduos)</h3>
          <div class="value">{int(qtd_m)}</div>
          <div class="sub">Soma de <span class="k">Total M</span></div>
        </div>""", unsafe_allow_html=True)

with t2:
    st.markdown(f"""
        <div class="card">
          <h3>♀️ Fêmeas (indivíduos)</h3>
          <div class="value">{int(qtd_f)}</div>
          <div class="sub">Soma de <span class="k">Total F</span></div>
        </div>""", unsafe_allow_html=True)

with t3:
    st.markdown(f"""
        <div class="card">
          <h3>👥 Animais totais</h3>
          <div class="value">{int(total_individuos)}</div>
          <div class="sub">Soma de <span class="k">Total Animais</span></div>
        </div>""", unsafe_allow_html=True)
# ---- Atalhos (botões) ----
st.markdown("""
<style>
div.stButton > button { width: 100%; padding: .75rem 1rem; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

def go(label: str, page_path: str, icon: str = "", primary: bool = False):
    btn = f"{icon} {label}".strip()
    if st.button(btn, use_container_width=True, type=("primary" if primary else "secondary")):
        st.switch_page(page_path)

go("Lotes",         "pages/1_Lotes.py",        icon="✅", primary=True)
go("Criar Lote",    "pages/2_Criar_Lote.py",   icon="🆕")
go("Planilha",      "pages/3_Planilha.py",     icon="📑")
go("Editar",        "pages/4_Editar.py",       icon="✏️")
go("Imprimir",      "pages/5_Imprimir.py",     icon="🖨️")
go("Animais Fora",  "pages/6_Animais_Fora.py", icon="🐄")
go("Duplicatas",    "pages/7_Duplicatas.py",   icon="🧩")
go("Dados",         "pages/8_Dados.py",        icon="🗂️")
go("Backup",        "pages/9_Backup.py",       icon="💾")
