import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO

from ui_nav import hide_default_sidebar_nav, render_sidebar_nav  # sidebar custom

st.set_page_config(page_title="Dados", page_icon="🗂️", layout="wide")
hide_default_sidebar_nav()
render_sidebar_nav()

st.title("🗂️ Dados")
st.markdown("Carregue um arquivo com os dados do leilão (HTML, Excel, LibreOffice etc.).")

COLUNAS_OBRIGATORIAS = [
    "N.º Série", "Data Emissão", "Proprietário Origem", "Município Origem",
    "M 0 - 8", "F 0 - 8", "M 9 - 12", "F 9 - 12",
    "M 13 - 24", "F 13 - 24", "M 25 - 36", "F 25 - 36",
    "M 36 +", "F 36 +", "Total M", "Total F", "Total Animais", "Lacre"
]

uploaded_file = st.file_uploader("📤 Selecione o arquivo", type=["xlsx", "xls", "ods", "html"])

def read_html_table(file):
    """
    Tenta ler a primeira tabela de um HTML usando lxml; se falhar, tenta bs4+html5lib.
    """
    # try lxml first
    try:
        file.seek(0)
        tables = pd.read_html(file, flavor="lxml")
        if not tables:
            raise ValueError("Nenhuma tabela encontrada no HTML (lxml).")
        return tables[0]
    except Exception as e_lxml:
        # fallback: bs4 + html5lib
        try:
            file.seek(0)
            tables = pd.read_html(file, flavor="bs4")
            if not tables:
                raise ValueError("Nenhuma tabela encontrada no HTML (bs4).")
            return tables[0]
        except Exception as e_bs4:
            raise RuntimeError(
                "Falha ao ler HTML. Instale as dependências: "
                "`pip install lxml` ou `pip install beautifulsoup4 html5lib`.\n"
                f"Detalhes lxml: {e_lxml}\nDetalhes bs4/html5lib: {e_bs4}"
            )

def carregar_dataframe(uploaded_file):
    ext = uploaded_file.name.split(".")[-1].lower()
    if ext == "html":
        return read_html_table(uploaded_file)
    elif ext in ["xlsx", "xls"]:
        try:
            uploaded_file.seek(0)
            return pd.read_excel(uploaded_file)  # usa openpyxl (xlsx) / xlrd (xls) se instalados
        except ImportError as e:
            raise RuntimeError(
                "Dependências para Excel não encontradas. "
                "Instale com: `pip install openpyxl xlrd`.\n" + str(e)
            )
    elif ext == "ods":
        try:
            uploaded_file.seek(0)
            return pd.read_excel(uploaded_file, engine="odf")
        except ImportError as e:
            raise RuntimeError(
                "Dependência para ODS não encontrada. "
                "Instale com: `pip install odfpy`.\n" + str(e)
            )
    else:
        raise RuntimeError("❌ Tipo de arquivo não suportado.")

# --- UI principal ---
if uploaded_file:
    try:
        df = carregar_dataframe(uploaded_file)

        colunas_arquivo = df.columns.tolist()
        faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in colunas_arquivo]
        if faltantes:
            st.error(f"❌ Colunas obrigatórias faltando no arquivo: {faltantes}")
            st.stop()

        df_filtrado = df[COLUNAS_OBRIGATORIAS].copy()
        st.success("✅ Arquivo carregado com sucesso.")
        st.dataframe(df_filtrado, use_container_width=True)
        st.session_state["df_filtrado"] = df_filtrado

    except Exception as e:
        st.error("❌ Erro ao processar o arquivo.")
        st.exception(e)
else:
    st.info("Nenhum arquivo selecionado ainda.")
    st.session_state.pop("df_filtrado", None)

# --- Info sobre REPLACE + confirmação ---
def _db_count():
    try:
        with sqlite3.connect("dados.db") as conn:
            return conn.execute("SELECT COUNT(1) FROM animais").fetchone()[0]
    except Exception:
        return None

qtd_atual = _db_count()
if qtd_atual is None:
    st.caption("📄 A tabela **animais** ainda não existe no banco.")
else:
    st.caption(f"📄 Registros atuais em **animais**: **{qtd_atual}**")

st.warning(
    "⚠️ **Atenção:** salvar irá **substituir completamente** a tabela **animais** "
    "no banco `dados.db` (`if_exists='replace'`). Todos os dados atuais serão **perdidos** "
    "e substituídos **apenas** pelos registros do arquivo carregado."
)

confirm = st.checkbox(
    "Sim, entendo as consequências e desejo **substituir** a tabela `animais`."
)

can_save = ("df_filtrado" in st.session_state) and confirm

if st.button("💾 Salvar no Banco de Dados", type="primary", disabled=not can_save):
    try:
        with sqlite3.connect("dados.db") as conn:
            st.session_state["df_filtrado"].to_sql("animais", conn, if_exists="replace", index=False)
        st.success("✅ Dados salvos com sucesso (tabela `animais` foi **substituída**).")
    except Exception as e:
        st.error("❌ Erro ao salvar os dados no banco.")
        st.exception(e)
