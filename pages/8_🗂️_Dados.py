import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO


st.set_page_config(page_title="Dados", page_icon="🗂️", layout="wide")
st.title("🗂️ Dados")

st.markdown("Carregue um arquivo com os dados do leilão (HTML, Excel, LibreOffice etc.).")

# Lista de colunas esperadas (validadas anteriormente)
COLUNAS_OBRIGATORIAS = [
    "N.º Série", "Data Emissão", "Proprietário Origem", "Município Origem",
    "M 0 - 8", "F 0 - 8", "M 9 - 12", "F 9 - 12",
    "M 13 - 24", "F 13 - 24", "M 25 - 36", "F 25 - 36",
    "M 36 +", "F 36 +", "Total M", "Total F", "Total Animais", "Lacre"
]

# Upload do arquivo
uploaded_file = st.file_uploader("📤 Selecione o arquivo", type=["xlsx", "xls", "ods", "html"])

if uploaded_file:
    try:
        # Detectar extensão
        ext = uploaded_file.name.split(".")[-1].lower()

        if ext == "html":
            df_list = pd.read_html(uploaded_file)
            df = df_list[0]
        elif ext in ["xlsx", "xls"]:
            df = pd.read_excel(uploaded_file)
        elif ext == "ods":
            df = pd.read_excel(uploaded_file, engine="odf")
        else:
            st.error("❌ Tipo de arquivo não suportado.")
            st.stop()

        # Validação de colunas
        colunas_arquivo = df.columns.tolist()
        faltantes = [col for col in COLUNAS_OBRIGATORIAS if col not in colunas_arquivo]

        if faltantes:
            st.error(f"❌ Colunas obrigatórias faltando no arquivo: {faltantes}")
            st.stop()

        # Exibir DataFrame filtrado
        df_filtrado = df[COLUNAS_OBRIGATORIAS]
        st.success("✅ Arquivo carregado com sucesso.")
        st.dataframe(df_filtrado, use_container_width=True)

    except Exception as e:
        st.exception(f"Erro ao processar o arquivo: {e}")
# Botão para salvar no banco
if st.button("💾 Salvar no Banco de Dados"):
    try:
        conn = sqlite3.connect("dados.db")
        df_filtrado.to_sql("animais", conn, if_exists="replace", index=False)
        conn.close()
        st.success("✅ Dados salvos com sucesso no banco 'dados.db'.")
    except Exception as e:
        st.error("❌ Erro ao salvar os dados no banco.")
        st.exception(e)
