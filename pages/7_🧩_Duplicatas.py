# pages/7_🧩_Duplicatas.py
from __future__ import annotations

import io
import sqlite3
from pathlib import Path
from typing import List, Tuple, Dict, Any

import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None  # evita crash se pandas não estiver instalado

# ------------------ Config da página ------------------
st.set_page_config(page_title="🧩 Duplicatas", page_icon="🧩", layout="wide")

# Navegação (topo)
st.page_link("🏠_Início.py", label="⬅️ Voltar para Início", icon="🏠", use_container_width=True)

APP_DIR = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path(".")
DB_PATH = APP_DIR / "dados.db"

st.set_page_config(page_title="Duplicatas", page_icon="🧩", layout="wide")
st.title("🧩 Duplicatas")
# ------------------ Helpers ------------------
def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)

def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    )
    return cur.fetchone() is not None

def _columns(conn: sqlite3.Connection, table: str) -> List[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]

def _df_from_rows(rows: list[tuple], headers: list[str]):
    if pd is None:
        return None
    return pd.DataFrame.from_records(rows, columns=headers)

# ------------------ Consultas iniciais ------------------
with _connect() as conn:
    if not _table_exists(conn, "animais"):
        st.error("Tabela `animais` não encontrada no banco de dados.")
        st.stop()

    cols = _columns(conn, "animais")

    # Campos preferenciais (aparece primeiro se existir)
    preferidos = [
        "rowid",
        "N.º Série",
        "Lacre",
        "Proprietário Origem",
        "Idade",
        "Idade (meses)",
        "Sexo",
    ]
    mostrar = [c for c in preferidos if (c == "rowid" or c in cols)]

    # completa com demais campos até um limite (para não poluir a visualização)
    for c in cols:
        if c not in mostrar and c != "rowid":
            mostrar.append(c)
        if len(mostrar) >= 12:
            break

    # Grupos duplicados por Lacre (não vazios)
    grupos: list[tuple[str, int]] = conn.execute(
        """
        SELECT Lacre, COUNT(*) AS cnt
        FROM animais
        WHERE Lacre IS NOT NULL AND TRIM(Lacre) <> ''
        GROUP BY Lacre
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC, Lacre
        """
    ).fetchall()

# ------------------ Filtros ------------------
col_f1, col_f2 = st.columns([1.2, 1])
with col_f1:
    q = st.text_input("🔎 Buscar lacre (ou parte)", "", placeholder="ex.: 123, ABC...")
with col_f2:
    st.write("")  # alinhamento
    st.write("**Duplicatas encontradas:**", len(grupos))

if q:
    grupos = [g for g in grupos if q.lower() in str(g[0]).lower()]

# Link prático para Backup (detecta se tem emoji no nome do arquivo)
backup_path = "pages/5_💾_Backup.py" if Path("pages/5_💾_Backup.py").exists() else (
    "pages/5_Backup.py" if Path("pages/5_Backup.py").exists() else None
)

if not grupos:
    st.info("Nenhuma duplicata encontrada (ou o filtro não retornou resultados).")
    if backup_path:
        st.page_link(backup_path, label="💾 Ir para Backup", icon="💾", use_container_width=True)
    st.stop()

# ------------------ Relatório geral (CSV) ------------------
if pd is not None:
    with _connect() as conn:
        all_rows: list[tuple] = []
        headers = ["Lacre", "rowid"] + [c for c in cols]
        for lacre, cnt in grupos:
            # pega todos registros do lacre
            rs = conn.execute(
                'SELECT ? as "Lacre", rowid, * FROM animais WHERE TRIM(Lacre)=? ORDER BY rowid',
                (str(lacre), str(lacre)),
            ).fetchall()
            all_rows.extend(rs)

        df_all = _df_from_rows(all_rows, headers)
        if df_all is not None and not df_all.empty:
            csv_all = df_all.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ Baixar CSV (todos os grupos)",
                data=csv_all,
                file_name="duplicatas_lacre.csv",
                use_container_width=True,
            )

st.divider()

# ------------------ Listagem por grupo ------------------
st.markdown("### Grupos de duplicados por **Lacre**")

for lacre, cnt in grupos:
    with st.expander(f"🔁 Lacre **{lacre}** — {cnt} registro(s)"):
        with _connect() as conn:
            # usa a lista 'mostrar' para não lotar a tabela
            select_cols = []
            if "rowid" in mostrar:
                select_cols.append("rowid")
            select_cols += [f'"{c}"' for c in mostrar if c != "rowid"]

            sql = f'SELECT {", ".join(select_cols)} FROM animais WHERE TRIM(Lacre)=? ORDER BY rowid'
            rows = conn.execute(sql, (str(lacre),)).fetchall()

        # headers “bonitos”
        headers = [c if c != '"rowid"' else "rowid" for c in select_cols]
        headers = [h.strip('"') for h in headers]

        if pd is not None:
            df = _df_from_rows(rows, headers)
            if df is not None and not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
                csv = df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "Baixar CSV deste grupo",
                    data=csv,
                    file_name=f"duplicatas_{lacre}.csv",
                    use_container_width=True,
                )
            else:
                st.info("Sem registros para exibir neste grupo.")
        else:
            # fallback sem pandas
            st.write(f"Campos: {', '.join(headers)}")
            st.write(rows)

st.divider()

# ------------------ Rodapé / navegação ------------------
st.page_link("🏠_Início.py", label="⬅️ Voltar para Início", icon="🏠", use_container_width=True)
if backup_path:
    st.page_link(backup_path, label="💾 Ir para Backup", icon="💾", use_container_width=True)
