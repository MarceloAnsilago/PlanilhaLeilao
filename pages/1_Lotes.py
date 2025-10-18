import streamlit as st
import sqlite3
from datetime import datetime
import html as html_lib
import base64
import streamlit.components.v1 as components

from ui_nav import hide_default_sidebar_nav, render_sidebar_nav  # sidebar custom

# ----------------- Config -----------------
st.set_page_config(page_title="Lotes", page_icon="✅", layout="wide")
hide_default_sidebar_nav()
render_sidebar_nav()
st.title("✅ Lotes")
st.caption("Clique em um card para alternar o status do lote. Pendentes aparecem primeiro.")

DB_PATH = "dados.db"

def abrir_pdf_nova_aba(pdf_bytes: bytes):
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    components.html(
        f"""
        <script>
        (function() {{
          try {{
            const b64 = "{b64}";
            const bin = atob(b64);
            const len = bin.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
            const blob = new Blob([bytes], {{ type: "application/pdf" }});
            const url = URL.createObjectURL(blob);
            const w = window.open("", "_blank");
            if (w) {{ w.location = url; }}
            else {{
              const a = document.createElement('a');
              a.href = url; a.target = "_blank"; a.click();
            }}
            setTimeout(() => URL.revokeObjectURL(url), 60000);
          }} catch (e) {{
            console.error("Falha ao abrir PDF:", e);
            alert("Não foi possível abrir o PDF. Faça o download.");
          }}
        }})();
        </script>
        """,
        height=0,
    )

# ----------------- DB helpers -----------------
def _connect():
    return sqlite3.connect(DB_PATH)

def _ensure_schema_lotes_status():
    with _connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS lotes (
            numero INTEGER PRIMARY KEY,
            criado_em TEXT,
            status TEXT NOT NULL DEFAULT 'pendente',
            concluido_em TEXT,
            gta_saida TEXT
        )""")
        cols = {r[1] for r in conn.execute("PRAGMA table_info(lotes)").fetchall()}
        if "status" not in cols:
            conn.execute("ALTER TABLE lotes ADD COLUMN status TEXT NOT NULL DEFAULT 'pendente'")
        if "concluido_em" not in cols:
            conn.execute("ALTER TABLE lotes ADD COLUMN concluido_em TEXT")
        if "gta_saida" not in cols:
            conn.execute("ALTER TABLE lotes ADD COLUMN gta_saida TEXT")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS lote_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lote_numero INTEGER NOT NULL,
            animal_rowid INTEGER NOT NULL,
            UNIQUE(lote_numero, animal_rowid)
        )""")
        conn.commit()

def _get_lote(numero: int):
    with _connect() as conn:
        r = conn.execute(
            "SELECT numero, status, criado_em, concluido_em, gta_saida FROM lotes WHERE numero=?",
            (int(numero),)
        ).fetchone()
    if r:
        return {"numero": r[0], "status": r[1], "criado_em": r[2], "concluido_em": r[3], "gta_saida": r[4]}
    return None

def _list_lotes():
    with _connect() as conn:
        rows = conn.execute("""
            SELECT L.numero,
                   COALESCE(L.status,'pendente') AS status,
                   L.criado_em,
                   L.gta_saida,
                   COUNT(I.id) AS itens
            FROM lotes L
            LEFT JOIN lote_itens I ON I.lote_numero = L.numero
            GROUP BY L.numero, L.status, L.criado_em, L.gta_saida
        """).fetchall()
    return [{"numero": r[0], "status": r[1], "criado_em": r[2], "gta_saida": r[3], "itens": r[4]} for r in rows]

def _set_lote_status(numero: int, status: str, gta_saida: str | None = None):
    status = "concluido" if status == "concluido" else "pendente"
    with _connect() as conn:
        if status == "concluido":
            conn.execute(
                "UPDATE lotes SET status=?, concluido_em=?, gta_saida=? WHERE numero=?",
                (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), gta_saida, int(numero)),
            )
        else:
            conn.execute(
                "UPDATE lotes SET status=?, concluido_em=NULL, gta_saida=NULL WHERE numero=?",
                (status, int(numero)),
            )
        conn.commit()

# ----------------- Bootstrap -----------------
_ensure_schema_lotes_status()

# ----------------- Query + Ordenação -----------------
lotes = _list_lotes()
pendentes  = sorted([l for l in lotes if l["status"] != "concluido"], key=lambda x: x["numero"])
concluidos = sorted([l for l in lotes if l["status"] == "concluido"], key=lambda x: x["numero"])

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
  background:#fff;
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
div[data-testid="stButton"] > button{
  width:100% !important; white-space:nowrap !important; height:42px !important; border-radius:12px !important;
}
/* bloco de confirmação — compacto e sem bordas extras */
.inline-confirm{ padding:6px 0 2px 0; margin-top:6px; }
.inline-row{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.inline-row > div{ flex:1 1 180px; }
.inline-small{ font-size:.85rem; padding:6px 10px; height:auto !important; }
</style>
""", unsafe_allow_html=True)

# ----------------- Estado -----------------
if "pending_action" not in st.session_state:
    st.session_state["pending_action"] = None
if "pending_gta" not in st.session_state:
    st.session_state["pending_gta"] = ""

def _open_conclude_dialog(numero: int):
    st.session_state["pending_action"] = {"type": "concluir", "numero": int(numero)}
    st.session_state["pending_gta"] = ""

def _open_reopen_dialog(numero: int):
    st.session_state["pending_action"] = {"type": "reabrir", "numero": int(numero)}

def _close_dialog():
    st.session_state["pending_action"] = None
    st.session_state["pending_gta"] = ""

# ----------------- UI helpers -----------------
def _render_inline_confirm(numero: int, tipo: str, gta_atual: str | None = None):
    """Painel compacto dentro do card do 'numero'."""
    with st.container():
        st.markdown('<div class="inline-confirm">', unsafe_allow_html=True)

        if tipo == "concluir":
            # apenas o input + botões (sem rótulo/linha extra)
            st.session_state["pending_gta"] = st.text_input(
                "Nº da GTA (opcional)",
                value=st.session_state.get("pending_gta",""),
                key=f"gta_input_{numero}",
                placeholder="Informe o n° da GTA de saida ex: 010101-E",
                label_visibility="collapsed",
            )
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                if st.button("💾 Salvar", key=f"btn_save_concluir_{numero}", use_container_width=True):
                    _set_lote_status(numero, "concluido", (st.session_state["pending_gta"] or None))
                    _close_dialog(); st.rerun()
            with c2:
                if st.button("✔️ Concluir", key=f"btn_concluir_sem_gta_{numero}", use_container_width=True):
                    _set_lote_status(numero, "concluido", None)
                    _close_dialog(); st.rerun()
            with c3:
                if st.button("Cancelar", key=f"btn_cancel_concluir_{numero}", use_container_width=True):
                    _close_dialog(); st.rerun()

        elif tipo == "reabrir":
            # mensagem curta + botões
            if gta_atual:
                st.caption(f"GTA {gta_atual} será excluída ao reabrir.")
            c1, c2 = st.columns([1,1])
            with c1:
                lbl = "↩️ Reabrir e excluir GTA" if gta_atual else "↩️ Reabrir"
                if st.button(lbl, key=f"btn_reabrir_{numero}", use_container_width=True):
                    _set_lote_status(numero, "pendente")
                    _close_dialog(); st.rerun()
            with c2:
                if st.button("Cancelar", key=f"btn_cancel_reabrir_{numero}", use_container_width=True):
                    _close_dialog(); st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

# ----------------- Grid -----------------
def _render_grid(items_list):
    if not items_list: return
    COLS = 4
    rows = (len(items_list) + COLS - 1) // COLS
    idx = 0
    for _ in range(rows):
        cols = st.columns(COLS)
        for c in cols:
            if idx >= len(items_list): break
            lote = items_list[idx]; idx += 1

            numero = lote["numero"]
            status = lote["status"]
            itens  = lote["itens"]
            gta    = lote.get("gta_saida") or None

            done = (status == "concluido")
            badge_text = "☑ Concluído" if done else "☐ Pendente"
            badge_cls  = "ok" if done else "pending"
            card_cls   = "card-concluido" if done else "card-pendente"
            extra_meta = f" • GTA: <b>{html_lib.escape(gta)}</b>" if (done and gta) else ""

            with c:
                st.markdown(
f"""
<div class="card-lote {card_cls}">
  <span class="ribbon">{'Concluído' if done else 'Pendente'}</span>
  <div class="title">Lote #{numero}</div>
  <div class="meta">Itens: <b>{itens}</b>{extra_meta}</div>
  <div style="margin-top:8px;"><span class="badge {badge_cls}">{badge_text}</span></div>
</div>
""", unsafe_allow_html=True)

                # linha de botões
                b1, b2 = st.columns([1,1])
                with b1:
                    toggle_label = "↩️ Reabrir" if done else "✅ Concluir"
                    if st.button(toggle_label, key=f"toggle_{numero}", use_container_width=True):
                        if done: _open_reopen_dialog(numero)
                        else:    _open_conclude_dialog(numero)
                with b2:
                    if st.button("🖨️ Imprimir", key=f"imprimir_{numero}", use_container_width=True):
                        try:
                            st.query_params.clear(); st.query_params["lote"] = str(numero)
                        except Exception:
                            st.experimental_set_query_params(lote=numero)
                        st.session_state["lote_para_imprimir"] = int(numero)
                        st.switch_page("pages/5_Imprimir.py")

                # confirmação ancorada ao card acionado
                pa = st.session_state.get("pending_action")
                if pa and pa.get("numero") == numero:
                    _render_inline_confirm(numero, pa.get("type"), gta_atual=gta)

# ----------------- Render -----------------
if pendentes: _render_grid(pendentes)

if concluidos:
    st.write(f"**Resumo:** {len(pendentes)} pendente(s) • {len(concluidos)} concluído(s).")
    st.divider(); st.markdown("**Concluídos**")
    _render_grid(concluidos)

st.divider()
st.write(f"**Resumo:** {len(pendentes)} pendente(s) • {len(concluidos)} concluído(s).")
