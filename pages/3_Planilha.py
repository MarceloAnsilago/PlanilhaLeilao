import streamlit as st
import pandas as pd
import sqlite3

from ui_nav import hide_default_sidebar_nav, render_sidebar_nav  # sidebar custom

st.set_page_config(page_title="Planilha", page_icon="📑", layout="wide")

# sidebar com ícones (esconde a nativa)
hide_default_sidebar_nav()
render_sidebar_nav()

st.title("📑 Planilha")
def _connect():
    return sqlite3.connect("dados.db")

with _connect() as conn:
    try:
        df = pd.read_sql("SELECT rowid, * FROM animais", conn)
    except Exception as e:
        st.info("ℹ️ Ainda não há a tabela **animais** no banco (ou está vazia). Importe/insira registros para visualizar aqui.")
        st.stop()

if df.empty:
    st.warning("⚠️ Nenhum dado encontrado na tabela **animais**.")
    st.stop()

if df.empty:
    st.warning("⚠️ Nenhum dado encontrado no banco.")
    st.stop()

st.markdown("### Registros salvos")

# Busca por caracteres (filtrar por lacre, nome ou série)
search = st.text_input("Pesquisar por lacre, nome ou série", value="", placeholder="Digite parte do lacre, nome do proprietário ou nº de série")

# se houver texto de busca, filtra o DataFrame (case-insensitive, substring)
if search:
    s = search.strip().lower()
    def _match(row):
        # tenta obter valores possíveis e verificar se s está contido
        lacre = str(row.get('Lacre', '') or '')
        nome = str(row.get('Proprietário Origem', '') or '')
        serie = str(row.get('N.º Série', '') or '')
        return (s in lacre.lower()) or (s in nome.lower()) or (s in serie.lower())

    df = df[df.apply(_match, axis=1)]

st.markdown("### Registros salvos")

for _, row in df.iterrows():
    left, right = st.columns([8, 1])
    # montar linha principal incluindo Lacre
    lacre_display = row.get('Lacre', '')
    serie_display = row.get('N.º Série', '(sem nº)')
    proprietario = row.get('Proprietário Origem', '')
    municipio = row.get('Município Origem', '')

    left.markdown(
        f"**{serie_display}** — {proprietario} ({municipio})"
    )
    # exibir lacre abaixo em fonte menor
    if lacre_display not in (None, ""):
        left.caption(f"Lacre: {lacre_display}")

    if right.button("✏️ Editar", key=f"ed_{row['rowid']}"):
        rid = str(int(row["rowid"]))
        st.session_state["last_rowid"] = rid           # backup
        st.query_params.clear()
        st.query_params["rowid"] = rid                 # vai pré-preencher o text_input na Editar
        st.switch_page("pages/4_Editar.py")
