import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

st.set_page_config(page_title="Criar Lote", page_icon="🆕", layout="wide")
st.title("🆕 Criar Lote")

# ---------------- utilitários ----------------
DB_PATH = "dados.db"

def _connect():
    return sqlite3.connect(DB_PATH)

def _ensure_schema():
    with _connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS lotes (
            numero INTEGER PRIMARY KEY,
            criado_em TEXT
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS lote_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lote_numero INTEGER NOT NULL,
            animal_rowid INTEGER NOT NULL,
            UNIQUE(lote_numero, animal_rowid)
        )""")
        conn.commit()

def _lote_exists(numero: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("SELECT 1 FROM lotes WHERE numero = ?", (numero,))
        return cur.fetchone() is not None

def _get_lote_itens(numero: int) -> list[int]:
    with _connect() as conn:
        cur = conn.execute("SELECT animal_rowid FROM lote_itens WHERE lote_numero = ? ORDER BY id", (numero,))
        return [r[0] for r in cur.fetchall()]

def _upsert_lote(numero: int):
    with _connect() as conn:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT OR IGNORE INTO lotes(numero, criado_em) VALUES(?, ?)", (numero, now))
        conn.commit()

def _save_lote_itens(numero: int, rowids: list[int]):
    if not rowids:
        return
    with _connect() as conn:
        for rid in rowids:
            conn.execute(
                "INSERT OR IGNORE INTO lote_itens(lote_numero, animal_rowid) VALUES(?, ?)",
                (numero, int(rid))
            )
        conn.commit()

def _remove_lote_item(numero: int, animal_rowid: int):
    with _connect() as conn:
        conn.execute("DELETE FROM lote_itens WHERE lote_numero = ? AND animal_rowid = ?", (numero, int(animal_rowid)))
        conn.commit()

def _delete_lote(numero: int):
    """Exclui TODA a estrutura do lote: itens e o próprio lote."""
    with _connect() as conn:
        conn.execute("DELETE FROM lote_itens WHERE lote_numero = ?", (numero,))
        conn.execute("DELETE FROM lotes WHERE numero = ?", (numero,))
        conn.commit()

def _fetch_animal_by_lacre(lacre_text: str) -> pd.DataFrame:
    """
    Busca por Lacre aceitando texto ou inteiro.
    """
    q = str(lacre_text).strip()
    if not q:
        return pd.DataFrame()
    with _connect() as conn:
        try:
            df = pd.read_sql(
                """
                SELECT rowid, * 
                FROM animais
                WHERE CAST(Lacre AS TEXT) = ?
                   OR Lacre = CAST(? AS INTEGER)
                """,
                conn, params=(q, q)
            )
        except Exception:
            df = pd.DataFrame()
    return df

def _fetch_animais_by_rowids(rowids: list[int]) -> pd.DataFrame:
    if not rowids:
        return pd.DataFrame()
    with _connect() as conn:
        df = pd.read_sql(
            f"SELECT rowid, * FROM animais WHERE rowid IN ({','.join(['?']*len(rowids))})",
            conn, params=tuple(rowids)
        )
    order = {rid: i for i, rid in enumerate(rowids)}
    df["__ord"] = df["rowid"].map(order)
    df = df.sort_values("__ord").drop(columns=["__ord"])
    return df

def _lotes_of_animal(animal_rowid: int) -> list[int]:
    with _connect() as conn:
        cur = conn.execute("SELECT DISTINCT lote_numero FROM lote_itens WHERE animal_rowid = ?", (int(animal_rowid),))
        return [r[0] for r in cur.fetchall()]

# -------------- estado da página --------------
_ensure_schema()
if "lote_numero" not in st.session_state:
    st.session_state.lote_numero = None
if "lote_buffer" not in st.session_state:
    st.session_state.lote_buffer = []   # lista de rowids (pendentes)
if "busca_lacre" not in st.session_state:
    st.session_state.busca_lacre = ""
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = False  # controle do fluxo de confirmação de exclusão

# Layout centralizado: uma coluna única no centro da página
center_cols = st.columns([1, 8, 1])
with center_cols[1].container():
    st.subheader("Criar / Gerenciar Lote")

    # =========================
    # Expander 1 — Selecionar/Carregar
    # =========================
    with st.expander("🎛️ Selecionar / Carregar Lote", expanded=True):
        numero_lote = st.number_input("Número do lote", min_value=1, step=1, format="%d", key="numero_lote_input")
        btn_center = st.columns([2, 4, 2])
        if btn_center[1].button("📥 Carregar Lote", key="carregar_lote"):
            if not numero_lote:
                st.error("Informe um número de lote válido.")
            else:
                st.session_state.lote_numero = int(numero_lote)
                st.session_state.confirm_delete = False  # reset do fluxo de exclusão
                if _lote_exists(st.session_state.lote_numero):
                    saved_count = len(_get_lote_itens(st.session_state.lote_numero))
                    st.session_state.lote_buffer = []  # não puxar salvos pro buffer
                    st.success(f"Lote {st.session_state.lote_numero} carregado ({saved_count} itens salvos).")
                else:
                    st.session_state.lote_buffer = []
                    st.info(f"Lote {st.session_state.lote_numero} ainda não existe. Você pode criar e adicionar lacres.")

    st.divider()

    # =========================
    # Expander 2 — Inserir Lacres
    # =========================
    with st.expander(f"🧷 Lote #{st.session_state.lote_numero if st.session_state.lote_numero else '—'} — Inserir Lacres", expanded=True):
        st.session_state.busca_lacre = st.text_input("Lacre", key="lacre_input", placeholder="Digite o número do lacre")
        s_btn = st.columns([2, 4, 2])
        if s_btn[1].button("🔍 Buscar por Lacre", key="buscar_lacre"):
            pass  # a busca usa a string em session_state

        df_busca = _fetch_animal_by_lacre(st.session_state.busca_lacre)
        if st.session_state.busca_lacre and df_busca.empty:
            st.warning("Nenhum registro encontrado para este lacre.")

        if not df_busca.empty:
            st.markdown("**Resultado da busca:**")
            for _, r in df_busca.iterrows():
                rid = int(r["rowid"])
                nserie = r.get("N.º Série", "")
                nome = r.get("Proprietário Origem", "")
                muni = r.get("Município Origem", "")
                lacre = r.get("Lacre", "")
                st.markdown(f"**Série {nserie} — Lacre {lacre}** — {nome} ({muni})")

                # --- Checagem ADIANTADA: já pertence a algum lote? (inclui este)
                lotes_existentes = _lotes_of_animal(rid) if st.session_state.lote_numero else []
                can_insert = True
                if lotes_existentes:
                    if st.session_state.lote_numero in lotes_existentes:
                        st.info("Este item **já está salvo neste lote**.", icon="ℹ️")
                        can_insert = False
                    else:
                        st.warning(f"❗ Este lacre já pertence ao(s) lote(s): {', '.join(map(str, lotes_existentes))}. Não é possível inserir aqui.")
                        can_insert = False

                ins_btn = st.columns([2, 4, 2])
                if ins_btn[1].button("➕ Inserir no lote", key=f"ins_{rid}", disabled=not can_insert):
                    if not st.session_state.lote_numero:
                        st.error("Selecione um lote antes de inserir itens.")
                    else:
                        # Não rechecamos aqui: já foi checado acima. Apenas evita duplicar no buffer.
                        if rid not in st.session_state.lote_buffer:
                            st.session_state.lote_buffer.append(rid)
                            st.success("Item inserido no lote (pendente).")
                        else:
                            st.info("Este item já está pendente neste lote.")

    # =========================
    # Expander 3 — Itens do Lote (Pendentes x Salvos)
    # =========================
    # Itens salvos no banco
    rowids_salvos = _get_lote_itens(st.session_state.lote_numero) if st.session_state.lote_numero else []
    df_salvos = _fetch_animais_by_rowids(rowids_salvos) if rowids_salvos else pd.DataFrame()

    # Pendentes = buffer - salvos
    pendentes = [int(rid) for rid in st.session_state.lote_buffer if int(rid) not in set(rowids_salvos)]
    df_buffer = _fetch_animais_by_rowids(pendentes)

    with st.expander(f"📦 Itens do Lote — pendentes: {len(pendentes)} | salvos: {len(rowids_salvos)}", expanded=True):
        # PENDENTES
        st.markdown("### Pendentes")
        if df_buffer.empty:
            st.caption("Nenhum item pendente. Busque um lacre e clique em Inserir.")
        else:
            st.write("Use **Salvar** para gravar no banco ou **Remover** para tirar dos pendentes.")
            for rid in list(pendentes):
                row = df_buffer.loc[df_buffer['rowid'] == rid] if 'rowid' in df_buffer.columns else None
                serie = row['N.º Série'].values[0] if row is not None and not row.empty and 'N.º Série' in row.columns else ''
                lacre = row['Lacre'].values[0] if row is not None and not row.empty and 'Lacre' in row.columns else ''
                # layout: descrição | Salvar | Remover (larguras para evitar quebra)
                cols = st.columns([7, 2, 2])
                cols[0].markdown(f"{rid} — Série {serie} — **Lacre {lacre}**")

                # botão SALVAR imediato
                if cols[1].button("💾 Salvar", key=f"save_pend_{rid}"):
                    if not st.session_state.lote_numero:
                        st.error("Nenhum número de lote selecionado.")
                    else:
                        try:
                            _upsert_lote(st.session_state.lote_numero)
                            _save_lote_itens(st.session_state.lote_numero, [int(rid)])
                            st.session_state.lote_buffer = [r for r in st.session_state.lote_buffer if int(r) != int(rid)]
                            st.success(f"Item salvo no lote {st.session_state.lote_numero}.")
                            st.rerun()
                        except Exception as e:
                            st.error("❌ Erro ao salvar este item.")
                            st.exception(e)

                # botão REMOVER do buffer
                if cols[2].button("➖ Remover", key=f"rem_pend_{rid}"):
                    st.session_state.lote_buffer = [r for r in st.session_state.lote_buffer if int(r) != int(rid)]
                    st.rerun()

                st.markdown("<hr style='margin:0.5rem 0; opacity:0.15'>", unsafe_allow_html=True)

        st.markdown("---")

        # SALVOS
        st.markdown("### Salvos")
        if not st.session_state.lote_numero:
            st.caption("Selecione ou carregue um lote para ver os itens salvos.")
        else:
            if df_salvos.empty:
                st.caption("Ainda não há itens salvos neste lote.")
            else:
                st.write("Clique em **Remover** ao lado do item que deseja excluir do lote (salvo).")
                for rid in rowids_salvos:
                    row = df_salvos.loc[df_salvos['rowid'] == rid] if 'rowid' in df_salvos.columns else None
                    serie = row['N.º Série'].values[0] if row is not None and not row.empty and 'N.º Série' in row.columns else ''
                    lacre = row['Lacre'].values[0] if row is not None and not row.empty and 'Lacre' in row.columns else ''
                    cols = st.columns([8, 1])
                    cols[0].markdown(f"{rid} — Série {serie} — **Lacre {lacre}**")
                    if cols[1].button("🗑️ Remover", key=f"rem_sal_{rid}"):
                        _remove_lote_item(st.session_state.lote_numero, int(rid))
                        st.success("Item removido do lote.")
                        st.rerun()

    st.divider()

    # =========================
    # Rodapé — Salvar Lote & Excluir Lote
    # =========================
    footer = st.columns([3, 2, 2, 3])
    # Salvar Lote
    if footer[1].button("💾 Salvar Lote", key="salvar_lote"):
        if not st.session_state.lote_numero:
            st.error("Nenhum número de lote selecionado.")
        else:
            try:
                _upsert_lote(st.session_state.lote_numero)
                _save_lote_itens(st.session_state.lote_numero, pendentes)  # só os novos
                st.success(f"Lote {st.session_state.lote_numero} salvo com {len(pendentes)} item(ns) novo(s).")
                st.session_state.lote_buffer = []  # limpa pendentes
                st.rerun()
            except Exception as e:
                st.error("❌ Erro ao salvar o lote.")
                st.exception(e)

    # Excluir Lote (passo 1: acionar confirmação)
    excluir_disabled = (st.session_state.lote_numero is None)
    if footer[2].button("🗑️ Excluir Lote", key="excluir_lote", disabled=excluir_disabled):
        if st.session_state.lote_numero is None:
            st.error("Nenhum número de lote selecionado.")
        else:
            st.session_state.confirm_delete = True

    # Bloco de confirmação (passo 2)
    if st.session_state.confirm_delete and st.session_state.lote_numero is not None:
        st.warning(
            f"⚠️ **Atenção**: Esta ação **NÃO poderá ser desfeita**.\n\n"
            f"Isto irá excluir **todos os itens** do lote **{st.session_state.lote_numero}** e o **próprio lote**.",
            icon="⚠️"
        )
        conf_cols = st.columns([3, 2, 2, 3])
        if conf_cols[1].button("✅ Confirmar exclusão", key="confirmar_excluir_lote"):
            try:
                _delete_lote(st.session_state.lote_numero)
                st.success(f"Lote {st.session_state.lote_numero} e todos os seus itens foram excluídos.")
                # limpa estados
                st.session_state.lote_buffer = []
                st.session_state.lote_numero = None
                st.session_state.confirm_delete = False
                st.rerun()
            except Exception as e:
                st.error("❌ Erro ao excluir o lote.")
                st.exception(e)

        if conf_cols[2].button("↩️ Cancelar", key="cancelar_excluir_lote"):
            st.session_state.confirm_delete = False
