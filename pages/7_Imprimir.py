import re
import base64
import sqlite3
from io import BytesIO
from datetime import datetime
import html as html_lib
import streamlit as st

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics

DB_PATH = "dados.db"

st.set_page_config(page_title="Imprimir Lote", page_icon="🖨️", layout="wide")

# ---------- Faixas ---------- 
FAIXAS = [
    ("0–8",   (0, 8)),
    ("9–12",  (9, 12)),
    ("13–18", (13, 18)),
    ("19–24", (19, 24)),
    ("25–30", (25, 30)),
    ("31–36", (31, 36)),
    ("36+",   (37, 10_000)),
]
POSSIVEIS_COLS_IDADE = [
    "Idade", "Idade (meses)", "Idade_meses", "Meses", "Meses Idade",
    "Idade em meses", "Idade Em Meses"
]

# ---------- DB helpers ----------
def _connect():
    return sqlite3.connect(DB_PATH)

def _qp_lote():
    # lê ?lote= do URL (API nova e fallback)
    try:
        qp = st.query_params
        v = qp.get("lote")
        if isinstance(v, list): return v[0] if v else None
        return v
    except Exception:
        qp = st.experimental_get_query_params()
        return (qp.get("lote") or [None])[0]

def _session_lote_fallback():
    try:
        if "lote_para_imprimir" in st.session_state:
            return str(st.session_state.get("lote_para_imprimir"))
    except Exception:
        pass
    return None

def _fetch_lote(numero: int):
    with _connect() as conn:
        row = conn.execute(
            "SELECT numero, criado_em, COALESCE(status,'pendente'), concluido_em "
            "FROM lotes WHERE numero=?",
            (int(numero),)
        ).fetchone()
    if not row:
        return None
    return {"numero": row[0], "criado_em": row[1], "status": row[2], "concluido_em": row[3]}

def _get_animais_columns():
    with _connect() as conn:
        cols = conn.execute("PRAGMA table_info(animais)").fetchall()
    return [c[1] for c in cols]

# ---------- Normalização & detecção ----------
def _norm(s: str) -> str:
    s = (s or "")
    s = s.replace("–", "-").replace("—", "-").replace("−", "-")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def _coluna_idade_meses(cols_animais: list[str]) -> str | None:
    norm_cols = { _norm(c).lower(): c for c in cols_animais }
    for nome in POSSIVEIS_COLS_IDADE:
        nc = _norm(nome).lower()
        for dbn, original in norm_cols.items():
            if nc == dbn or nc in dbn:
                return original
    return None

def _faixa_por_idade(meses) -> str | None:
    if meses is None: return None
    try:
        m = float(meses)
    except Exception:
        return None
    for label, (lo, hi) in FAIXAS:
        if label == "36+" and m >= 37: return "36+"
        if lo <= m <= hi: return label
    return None

R_RANGE = re.compile(r"^(M|F)\s*(\d{1,2})\s*-\s*(\d{1,2})$", re.IGNORECASE)
R_36P   = re.compile(r"^(M|F)\s*36\s*\+$", re.IGNORECASE)

def _detectar_cols_por_faixa_sexo(cols_animais: list[str]):
    encontrados = []
    for c in cols_animais:
        cname = _norm(c)
        m = R_RANGE.match(cname)
        if m:
            sexo = m.group(1).upper()
            lo   = int(m.group(2))
            hi   = int(m.group(3))
            encontrados.append((c, sexo, (lo, hi)))
            continue
        m = R_36P.match(cname)
        if m:
            sexo = m.group(1).upper()
            encontrados.append((c, sexo, (37, 10_000)))
    return encontrados

def _label_faixa_from_bounds(bounds: tuple[int,int]) -> list[str]:
    lo, hi = bounds
    for label, (a, b) in FAIXAS:
        if label == "36+" and lo >= 37: return [label]
        if lo == a and hi == b: return [label]
    if lo == 25 and hi == 36:
        return ["25–30", "31–36"]
    mid = (lo + hi) / 2.0
    best = min(FAIXAS, key=lambda x: abs(((x[1][0]+x[1][1])/2.0) - mid))[:1][0]
    return [best]

# ---------- Query agregada ----------
def _fetch_lote_agrupado(numero: int):
    cols_animais = _get_animais_columns()
    idade_col = _coluna_idade_meses(cols_animais)
    faixa_cols = _detectar_cols_por_faixa_sexo(cols_animais)

    selects = [
        'a."N.º Série" AS serie',
        'a.Lacre AS lacre',
        'a."Proprietário Origem" AS proprietario',
    ]
    if idade_col:
        selects.append(f'a."{idade_col}" AS idade_meses')
    for colname, _sx, _rng in faixa_cols:
        selects.append(f'a."{colname}" AS "{colname}"')

    sql = f"""
        SELECT {', '.join(selects)}
        FROM lote_itens li
        JOIN animais a ON a.rowid = li.animal_rowid
        WHERE li.lote_numero = ?
        ORDER BY li.id
    """

    with _connect() as conn:
        rows = conn.execute(sql, (int(numero),)).fetchall()
        desc = conn.execute(sql.replace("?", str(int(numero))) + " LIMIT 1").description if rows else []
        colnames = [d[0] for d in desc] if desc else [s.split(' AS ')[-1].strip('"') for s in selects]

    grupos = {}
    def _key(d):
        return (str(d.get("serie","")), str(d.get("lacre","")), str(d.get("proprietario","")))

    for r in rows:
        d = dict(zip(colnames, r))
        k = _key(d)
        if k not in grupos:
            grupos[k] = {
                "serie": d.get("serie",""),
                "lacre": d.get("lacre",""),
                "proprietario": d.get("proprietario",""),
                "M": {label: 0 for label, _ in FAIXAS},
                "F": {label: 0 for label, _ in FAIXAS},
            }

        for colname, sexo, bounds in _detectar_cols_por_faixa_sexo(colnames):
            raw = d.get(colname)
            try:
                val = int(str(raw).strip()) if raw not in (None, "") else 0
            except Exception:
                val = 0
            if val <= 0:
                continue

            labels = _label_faixa_from_bounds(bounds)
            if labels == ["25–30","31–36"]:
                if idade_col and d.get("idade_meses") not in (None,""):
                    lbl = _faixa_por_idade(d.get("idade_meses"))
                    if lbl in ("25–30","31–36"):
                        grupos[k][sexo][lbl] += val
                    else:
                        grupos[k][sexo]["25–30"] += val
                else:
                    grupos[k][sexo]["25–30"] += val
            else:
                for lbl in labels:
                    grupos[k][sexo][lbl] += val

    itens = list(grupos.values())
    def _to_int(x):
        try: return int(str(x))
        except: return 0
    itens.sort(key=lambda x: (_to_int(x["lacre"]), _to_int(x["serie"])))
    return itens

# ---------- util: truncar ----------
def truncate_text(text: str, max_width_pt: float, font_name: str = "Helvetica-Oblique", font_size: float = 8.0) -> str:
    if text is None:
        return ""
    t = str(text)
    if pdfmetrics.stringWidth(t, font_name, font_size) <= max_width_pt:
        return t
    ell = "…"
    ell_w = pdfmetrics.stringWidth(ell, font_name, font_size)
    lo, hi = 0, len(t)
    while lo < hi:
        mid = (lo + hi) // 2
        cand = t[:mid].rstrip() + ell
        w = pdfmetrics.stringWidth(cand, font_name, font_size)
        if w <= max_width_pt:
            lo = mid + 1
        else:
            hi = mid
    mid = max(0, lo - 1)
    return t[:mid].rstrip() + ell

# ---------- PDF ----------
def build_pdf(lote_info: dict, items: list[dict]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * mm,
        rightMargin=14 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"Lote #{lote_info['numero']}",
        author="Sistema de Lotes",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title_center", parent=styles["Title"], alignment=1, fontSize=20, leading=24, spaceAfter=6)
    legend_title = ParagraphStyle("legend", parent=styles["Heading4"], alignment=0, fontSize=12, leading=14)

    story = []
    story.append(Paragraph(f"Lote #{lote_info['numero']}", title))
    story.append(Spacer(1, 6))

    area_util_mm = (doc.pagesize[0] - doc.leftMargin - doc.rightMargin) / mm
    w_serie, w_lacre, w_prop = 24*mm, 18*mm, 62*mm
    remaining = (area_util_mm*mm) - (w_serie + w_lacre + w_prop)
    num_subcols = len(FAIXAS) * 2
    w_sub = max(7*mm, remaining / num_subcols)
    colWidths = [w_serie, w_lacre, w_prop] + [w_sub] * num_subcols

    left_pad = right_pad = 3
    avail_prop_width = w_prop - left_pad - right_pad

    head_top  = ["", "", ""]
    head_sub  = ["Série", "Lacre", "Proprietário"]
    for label, _ in FAIXAS:
        head_top += [label, ""]
        head_sub += ["M", "F"]
    data = [head_top, head_sub]

    for it in items:
        nome = it.get("proprietario","")
        nome_trunc = truncate_text(nome, avail_prop_width, "Helvetica-Oblique", 8.0)
        row = [it.get("serie",""), it.get("lacre",""), nome_trunc]
        for label, _ in FAIXAS:
            row.append(str(it["M"].get(label, 0)))
            row.append(str(it["F"].get(label, 0)))
        data.append(row)

    if len(data) == 2:
        data.append(["—"] * len(head_top))

    table = Table(data, colWidths=colWidths, hAlign="LEFT", repeatRows=2)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
        ("TEXTCOLOR",  (0, 0), (-1, 1), colors.HexColor("#111827")),
        ("FONTNAME",   (0, 0), (-1, 1), "Helvetica-Bold"),
        ("FONTNAME",   (0, 2), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 0), (-1, 0), 10),
        ("FONTSIZE",   (0, 1), (-1, 1), 9),
        ("FONTSIZE",   (0, 2), (-1, -1), 9),
        ("ALIGN",      (0, 0), (1, -1), "CENTER"),
        ("ALIGN",      (2, 0), (2, -1), "LEFT"),
        ("ALIGN",      (3, 0), (-1, -1), "CENTER"),
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,2), (-1,-1), [colors.white, colors.HexColor("#fafafa")]),
        ("FONTNAME",   (2, 2), (2, -1), "Helvetica-Oblique"),
        ("FONTSIZE",   (2, 2), (2, -1), 8),
        ("LEFTPADDING",(2, 2), (2, -1), left_pad),
        ("RIGHTPADDING",(2, 2), (2, -1), right_pad),
    ]
    start = 3
    for _label, _ in FAIXAS:
        style_cmds.append(("SPAN", (start, 0), (start+1, 0)))
        start += 2

    table.setStyle(TableStyle(style_cmds))
    story.append(table)
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Total de linhas (lacre): <b>{len(items)}</b>", styles["Normal"]))

    tot_M = {label: 0 for label, _ in FAIXAS}
    tot_F = {label: 0 for label, _ in FAIXAS}
    for it in items:
        for label, _ in FAIXAS:
            tot_M[label] += int(it["M"].get(label, 0))
            tot_F[label] += int(it["F"].get(label, 0))
    total_M_geral = sum(tot_M.values())
    total_F_geral = sum(tot_F.values())

    story.append(Spacer(1, 12))
    story.append(Paragraph("GTA de Saída", legend_title))
    story.append(Spacer(1, 4))

    gta_top = []
    gta_sub = []
    for label, _ in FAIXAS:
        gta_top += [label, ""]
        gta_sub += ["M", "F"]
    gta_top += ["Total", ""]
    gta_sub += ["M", "F"]

    gta_row = []
    for label, _ in FAIXAS:
        gta_row += [str(tot_M[label]), str(tot_F[label])]
    gta_row += [str(total_M_geral), str(total_F_geral)]

    num_subcols_gta = len(FAIXAS)*2 + 2
    area_util_mm = (doc.pagesize[0] - doc.leftMargin - doc.rightMargin) / mm
    w_gta = max(10*mm, (area_util_mm*mm) / num_subcols_gta)

    gta_table = Table([gta_top, gta_sub, gta_row], colWidths=[w_gta]*num_subcols_gta, hAlign="LEFT", repeatRows=2)
    gta_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME",   (0, 0), (-1, 1), "Helvetica-Bold"),
        ("FONTNAME",   (0, 2), (-1, 2), "Helvetica"),
        ("FONTSIZE",   (0, 0), (-1, 0), 10),
        ("FONTSIZE",   (0, 1), (-1, 1), 9),
        ("FONTSIZE",   (0, 2), (-1, 2), 10),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
    ]
    c = 0
    for _label, _ in FAIXAS:
        gta_style.append(("SPAN", (c, 0), (c+1, 0)))
        c += 2
    gta_style.append(("SPAN", (c, 0), (c+1, 0)))  # "Total"

    gta_table.setStyle(TableStyle(gta_style))
    story.append(gta_table)

    doc.build(story)
    return buf.getvalue()

# ---------- Página ----------
st.markdown("## 🖨️ Imprimir Lote")

lote_str = _qp_lote() or _session_lote_fallback()
if not lote_str:
    st.error("Parâmetro `?lote=` não informado.")
    st.stop()

try:
    lote_num = int(lote_str)
except Exception:
    st.error("Parâmetro `lote` inválido.")
    st.stop()

info = _fetch_lote(lote_num)
if not info:
    st.error(f"Lote #{lote_num} não encontrado.")
    st.stop()

items = _fetch_lote_agrupado(lote_num)
pdf_bytes = build_pdf(info, items)

# Botão para baixar o PDF
st.download_button("⬇️ Baixar PDF", data=pdf_bytes, file_name=f"Lote_{lote_num}.pdf", mime="application/pdf")

# --- exibir o PDF em HTML usando blob: (mais compatível que data:) ---
import base64
import streamlit.components.v1 as components

b64 = base64.b64encode(pdf_bytes).decode("utf-8")

components.html(
    f"""
    <div id="wrap" style="width:100%;height:820px;">
      <iframe id="pdfFrame" style="border:none;width:100%;height:100%;"></iframe>
    </div>
    <script>
      (function() {{
        try {{
          const b64 = "{b64}";
          const byteChars = atob(b64);
          const byteNums = new Array(byteChars.length);
          for (let i = 0; i < byteChars.length; i++) byteNums[i] = byteChars.charCodeAt(i);
          const byteArray = new Uint8Array(byteNums);
          const blob = new Blob([byteArray], {{ type: "application/pdf" }});
          const url = URL.createObjectURL(blob);
          const iframe = document.getElementById("pdfFrame");
          iframe.src = url;

          // opcional: link para abrir em nova aba
          const link = document.createElement("a");
          link.href = url;
          link.textContent = "🔗 Abrir PDF em nova aba";
          link.target = "_blank";
          link.style.display = "inline-block";
          link.style.marginTop = "8px";
          document.getElementById("wrap").insertAdjacentElement("afterend", link);
        }} catch (e) {{
          const el = document.createElement("div");
          el.textContent = "Falha ao carregar PDF inline. Use o botão de download.";
          el.style.color = "red";
          document.getElementById("wrap").appendChild(el);
          console.error(e);
        }}
      }})();
    </script>
    """,
    height=860,
)