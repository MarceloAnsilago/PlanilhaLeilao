import streamlit as st

st.set_page_config(page_title="Backup", page_icon="💾", layout="wide")

st.title("💾 Backup de Dados")
st.markdown("Faça o **download** ou o **upload** do backup do banco de dados.")

st.header("⬇️ Baixar Backup")

st.info("Quando implementado, aqui você poderá baixar o arquivo `.db` do SQLite contendo todos os dados salvos.")

st.download_button(
    label="Download do banco de dados",
    data=None,  # Temporariamente nulo – será substituído pela leitura real do arquivo
    file_name="backup.sqlite",
    disabled=True
)

st.divider()

st.header("⬆️ Restaurar Backup")

uploaded_file = st.file_uploader("Selecione um arquivo `.sqlite` para restaurar o banco de dados", type=["sqlite", "db"])

if uploaded_file:
    st.warning("⚠️ Funcionalidade de restauração ainda não implementada.")
    st.write(f"Arquivo recebido: `{uploaded_file.name}`")
