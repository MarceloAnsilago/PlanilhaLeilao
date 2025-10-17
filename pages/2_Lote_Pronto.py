import streamlit as st
import sqlite3
from datetime import datetime
import html as html_lib

# ----------------- Config -----------------
st.set_page_config(page_title="Lote Pronto", page_icon="✅", layout="wide")
st.title("✅ Lote Pronto")
st.caption("Clique em um card para alternar o status do lote. Pendentes aparecem primeiro.")

DB_PATH = "dados.db"

# ----------------- DB helpers -----------------
def _connect():
    return sqlite3.connect(DB_PATH)

def _ensure_schema_lotes_status():
    with _connect() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(lotes)").fetchall()}
        if "status" not in cols:
            conn.execute("ALTER TABLE lotes ADD COLUMN status TEXT NOT NULL DEFAULT 'pendente'")
        if "concluido_em" not in cols:
            conn.execute("ALTER TABLE lotes ADD COLUMN concluido_em TEXT")
        conn.commit()

def _list_lotes():
    with _connect() as conn:
        rows = conn.execute("""
            SELECT L.numero,
                   COALESCE(L.status,'pendente') AS status,
                   L.criado_em,
                   COUNT(I.id) AS itens
            FROM lotes L
            LEFT JOIN lote_itens I ON I.lote_numero = L.numero
            GROUP BY L.numero, L.status, L.criado_em
        """).fetchall()
    return [{"numero": r[0], "status": r[1], "criado_em": r[2], "itens": r[3]} for r in rows]

def _set_lote_status(numero: int, status: str):
    status = "concluido" if status == "concluido" else "pendente"
    with _connect() as conn:
        if status == "concluido":
            conn.execute(
                "UPDATE lotes SET status=?, concluido_em=? WHERE numero=?",
                (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(numero)),
            )
        else:
            conn.execute(
                "UPDATE lotes SET status=?, concluido_em=NULL WHERE numero=?",
                (status, int(numero)),
            )
        conn.commit()

# ----------------- Bootstrap -----------------
_ensure_schema_lotes_status()

# ----------------- Query + Ordenação -----------------
lotes = _list_lotes()
pendentes  = sorted([l for l in lotes if l["status"] != "concluido"], key=lambda x: x["numero"])
concluidos = sorted([l for l in lotes if l["status"] == "concluido"], key=lambda x: x["numero"])
ordered = pendentes + concluidos

# ----------------- Estilo -----------------
st.markdown("""
<style>
:root{
  --green-600:#15803d; --green-100:#dcfce7;
  --amber-600:#b45309; --amber-100:#fef3c7;
  --slate-300:#cbd5e1;
}
.card-lote{
  border:1px solid var(--slate-300);
  border-radius:18px;
  padding:16px 14px 12px 14px;
  box-shadow:0 10px 24px rgba(0,0,0,.06);
  transition:transform .08s ease, box-shadow .12s ease, opacity .2s ease;
  position:relative;
}
.card-lote:hover{ transform:translateY(-2px); box-shadow:0 14px 30px rgba(0,0,0,.09); }
.card-pendente{
  background:linear-gradient(135deg, var(--amber-100) 0%, #ffffff 40%);
  border-color:#f7d694;
}
.card-concluido{
  background:linear-gradient(135deg, var(--green-100) 0%, #ffffff 40%);
  border-color:#bfeecf; opacity:.55;
}
.ribbon{
  position:absolute; top:12px; right:12px;
  font-size:.72rem; padding:4px 8px; border-radius:999px;
  background:#fff; border:1px solid rgba(0,0,0,.06); color:#374151;
}
.title{ font-weight:800; font-size:1.25rem; letter-spacing:.2px; color:#1f2937; }
.meta{ color:#475569; font-size:.85rem; margin-top:2px;}
.badge{
  display:inline-block; padding:4px 10px; border-radius:999px;
  font-size:.8rem; font-weight:600; border:1px solid transparent;
}
.badge.pending{ background:#fff7ed; color:var(--amber-600); border-color:#fde2b3;}
.badge.ok{ background:#ecfdf5; color:var(--green-600); border-color:#b7f0d1;}

/* Botões do Streamlit com largura/altura iguais */
div[data-testid="stButton"] > button{
  width:100% !important;
  white-space:nowrap !important;
  height:42px !important;
  border-radius:12px !important;
}

/* Link button igual ao stButton */
div[data-testid="stLinkButton"] > a{
  width:100% !important;
  height:42px !important;
  border-radius:12px !important;
  white-space:nowrap !important;
  display:inline-flex !important;
  align-items:center !important;
  justify-content:center !important;
}
</style>
""", unsafe_allow_html=True)

# ----------------- UI -----------------
if not lotes:
    st.info("Nenhum lote cadastrado ainda.")
else:
    COLS = 4

    def _render_grid(items_list):
        # Renderiza uma lista de lotes em grid de COLS colunas
        if not items_list:
            return
        rows = (len(items_list) + COLS - 1) // COLS
        idx = 0
        for _ in range(rows):
            cols = st.columns(COLS)
            for c in cols:
                if idx >= len(items_list):
                    break
                lote = items_list[idx]; idx += 1

                numero = lote["numero"]
                status = lote["status"]
                items  = lote["itens"]
                criado = lote["criado_em"] or ""

                done = (status == "concluido")
                badge_text = "☑ Concluído" if done else "☐ Pendente"
                badge_cls  = "ok" if done else "pending"
                card_cls   = "card-concluido" if done else "card-pendente"

                with c:
                    st.markdown(
                        f"""
<div class="card-lote {card_cls}">
  <span class="ribbon">{'Concluído' if done else 'Pendente'}</span>
  <div class="title">Lote #{numero}</div>
  <div class="meta">Itens: <b>{items}</b> • Criado em: {html_lib.escape(criado)}</div>
  <div style="margin-top:8px;"><span class="badge {badge_cls}">{badge_text}</span></div>
</div>
""",
                        unsafe_allow_html=True
                    )

                    # Botões lado a lado, mesmo tamanho
                    b1, b2 = st.columns([1, 1])
                    with b1:
                        toggle_label = "↩️ Reabrir" if done else "✅ Concluir"
                        if st.button(toggle_label, key=f"toggle_{numero}", use_container_width=True):
                            _set_lote_status(numero, "pendente" if done else "concluido")
                            st.rerun()
                    with b2:
                        # Navegar para a página de impressão na mesma aba
                        if st.button("🖨️ Imprimir", key=f"imprimir_{numero}", use_container_width=True):
                            st.session_state["lote_para_imprimir"] = int(numero)
                            # troca de página interna (mesma aba)
                            st.switch_page("pages/7_Imprimir.py")

    # Renderizar pendentes primeiro
    if pendentes:
        _render_grid(pendentes)

    # Separador entre pendentes e concluídos
    if concluidos:
        st.divider()
        st.markdown("**Concluídos**")
        _render_grid(concluidos)

# ----------------- Rodapé -----------------
st.divider()
st.write(f"**Resumo:** {len(pendentes)} pendente(s) • {len(concluidos)} concluído(s).")
