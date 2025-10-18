# ui_nav.py
import streamlit as st

def hide_default_sidebar_nav():
    st.markdown("""
    <style>
      [data-testid="stSidebarNav"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

from pathlib import Path
import streamlit as st

def render_sidebar_nav():
    # escolhe o arquivo de entrada disponível
    if Path("Inicio.py").exists():
        home = "Inicio.py"
    elif Path("inicio.py").exists():
        home = "inicio.py"
    elif Path("main.py").exists():
        home = "main.py"
    else:
        home = "Inicio.py"  # padrão

    st.sidebar.markdown("### Navegação")
    st.sidebar.page_link(home,                       label="Início",        icon="🏠")
    st.sidebar.page_link("pages/1_Lotes.py",        label="Lotes",         icon="✅")
    st.sidebar.page_link("pages/2_Criar_Lote.py",   label="Criar Lote",    icon="🆕")
    st.sidebar.page_link("pages/3_Planilha.py",     label="Planilha",      icon="📑")
    st.sidebar.page_link("pages/4_Editar.py",       label="Editar",        icon="✏️")
    st.sidebar.page_link("pages/5_Imprimir.py",     label="Imprimir",      icon="🖨️")
    st.sidebar.page_link("pages/6_Animais_Fora.py", label="Animais Fora",  icon="🐄")
    st.sidebar.page_link("pages/7_Duplicatas.py",   label="Duplicatas",    icon="🧩")
    st.sidebar.page_link("pages/8_Dados.py",        label="Dados",         icon="🗂️")
    st.sidebar.page_link("pages/9_Backup.py",       label="Backup",        icon="💾")
