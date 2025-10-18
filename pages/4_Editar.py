import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date

from ui_nav import hide_default_sidebar_nav, render_sidebar_nav  # sidebar custom

# ----------------- Config -----------------
st.set_page_config(page_title="Editar", page_icon="✏️", layout="wide")

# sidebar com ícones (esconde a nativa)
hide_default_sidebar_nav()
render_sidebar_nav()

st.title("✏️ Editar")

# -------------------- Utilidades --------------------
def _connect():
    return sqlite3.connect("dados.db")

def _qp_one(name: str):
    v = st.query_params.get(name)
    return v[0] if isinstance(v, list) else v

def _load_row(conn, rid):
    return pd.read_sql(
        "SELECT rowid, * FROM animais WHERE rowid = ?",
        conn,
        params=(rid,),
    )

def _is_num(x):
    return isinstance(x, (int, float)) and not pd.isna(x)

def _is_date_like(v):
    if isinstance(v, (datetime, date)):
        return True
    if isinstance(v, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
            try:
                datetime.strptime(v, fmt)
                return True
            except:
                pass
    return False

def _to_str_dt(v):
    if isinstance(v, date) and not isinstance(v, datetime):
        return datetime(v.year, v.month, v.day).strftime("%Y-%m-%d")
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return str(v)

# -------------------- Dados base para seletor --------------------
with _connect() as conn:
    all_rows = pd.read_sql(
        "SELECT rowid, `N.º Série`, `Proprietário Origem` FROM animais ORDER BY rowid",
        conn
    )

if all_rows.empty:
    st.error("❌ Não há registros no banco.")
    st.stop()

options = all_rows["rowid"].astype(int).tolist()

# Pré-seleção: via URL ou fallback do session_state
preselect_qp = _qp_one("rowid")
if not preselect_qp and "last_rowid" in st.session_state:
    preselect_qp = st.session_state["last_rowid"]

# -------------------- Gestão de estado do text_input --------------------
# 1) Se foi solicitado limpar (de um clique anterior), limpe ANTES de criar o widget
if st.session_state.get("__clear_txt_rowid", False):
    st.session_state["txt_rowid"] = ""
    st.session_state["__clear_txt_rowid"] = False

# 2) Se ainda não existe txt_rowid no estado, inicialize com o preselect (se houver)
if "txt_rowid" not in st.session_state:
    st.session_state["txt_rowid"] = str(preselect_qp) if preselect_qp else ""

# 3) Renderiza o text_input controlado somente por key
txt_val = st.text_input(
    "ID do registro (prioritário)",
    key="txt_rowid",
    placeholder="Digite os caracteres ou deixe vazio para usar o seletor abaixo"
)

# -------------------- Selectbox (secundário) --------------------
default_index = 0
try:
    if preselect_qp and int(preselect_qp) in options:
        default_index = options.index(int(preselect_qp))
except Exception:
    pass

sel_val = st.selectbox(
    "Ou selecione o registro",
    options=options,
    index=default_index,
    format_func=lambda rid: (
        f"{rid} — Nº Série: "
        f"{all_rows.loc[all_rows['rowid']==rid, 'N.º Série'].values[0]}"
    ),
)

# -------------------- Botão Carregar --------------------
if st.button("Carregar"):
    chosen = (st.session_state.get("txt_rowid", "") or "").strip()
    if not chosen:
        chosen = str(int(sel_val))  # fallback

    # Validação
    if not chosen.isdigit() or int(chosen) not in options:
        st.error("❌ ID inválido. Informe um rowid existente.")
        st.stop()

    # Sinaliza para limpar o text_input no próximo run
    st.session_state["__clear_txt_rowid"] = True

    # Define o rowid na URL e rerun
    st.query_params["rowid"] = chosen
    st.rerun()

# -------------------- Se não houver rowid definido, aguarda clique --------------------
rowid = _qp_one("rowid")
if not rowid:
    st.info("Informe o ID acima ou selecione e clique em **Carregar**.")
    st.stop()

# -------------------- Carregar registro e formulário --------------------
with _connect() as conn:
    df = _load_row(conn, rowid)

if df.empty:
    st.error("❌ Registro não encontrado.")
    st.stop()

registro = df.iloc[0].to_dict()
st.subheader(f"Registro #{rowid}")

with st.form("editar_form"):
    novos = {}
    for col, val in registro.items():
        if col == "rowid":
            continue

        if _is_date_like(val):
            base = datetime.now().date()
            try:
                if isinstance(val, str):
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
                        try:
                            base = datetime.strptime(val, fmt).date()
                            break
                        except:
                            pass
                elif isinstance(val, datetime):
                    base = val.date()
                elif isinstance(val, date):
                    base = val
            except:
                pass
            novos[col] = st.date_input(col, value=base)

        elif _is_num(val):
            if isinstance(val, int):
                novos[col] = st.number_input(col, value=int(val), step=1, format="%d")
            else:
                try:
                    basef = float(val)
                except:
                    basef = 0.0
                novos[col] = st.number_input(col, value=basef, step=1.0)

        else:
            novos[col] = st.text_input(col, value="" if pd.isna(val) else str(val))

    ok = st.form_submit_button("💾 Alterar")

if ok:
    try:
        for k, v in list(novos.items()):
            if isinstance(v, (datetime, date)):
                novos[k] = _to_str_dt(v)

        set_clause = ", ".join([f"{c} = ?" for c in novos.keys()])
        values = list(novos.values()) + [rowid]

        with _connect() as conn:
            conn.execute(f"UPDATE animais SET {set_clause} WHERE rowid = ?", values)
            conn.commit()

        st.success("✅ Registro atualizado com sucesso.")
        st.page_link("pages/3_Planilha.py", label="⬅️ Voltar para Planilha")
    except Exception as e:
        st.error("❌ Erro ao atualizar o registro.")
        st.exception(e)
