# pages/5_Backup.py
from __future__ import annotations
import os
import io
import time
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
import streamlit as st

# --------------------------------------------------
# Config
# --------------------------------------------------
st.set_page_config(page_title="Backup", page_icon="💾", layout="wide")
st.title("💾 Backup")
st.markdown("Faça **download** do banco atual ou **restaure** a partir de um arquivo `.sqlite`/`.db`.")

# Caminhos
APP_DIR = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path(".")
DB_PATH = APP_DIR / "dados.db"
BACKUPS_DIR = APP_DIR / "backups"
BACKUPS_DIR.mkdir(exist_ok=True)

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def _fmt_bytes(n: int) -> str:
    for unit in ["B","KB","MB","GB","TB"]:
        if n < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"

def is_sqlite_file(buf_or_path) -> bool:
    """Checa header 'SQLite format 3\\0' + abre e roda um integrity_check."""
    try:
        if isinstance(buf_or_path, (str, os.PathLike, Path)):
            p = Path(buf_or_path)
            if not p.exists():
                return False
            with p.open("rb") as f:
                header = f.read(16)
            tmp_path = p  # validaremos com conexão logo abaixo
        else:
            # Uploaded file-like
            pos = buf_or_path.tell()
            buf_or_path.seek(0)
            header = buf_or_path.read(16)
            buf_or_path.seek(pos)
            # gravar temporariamente para testar com sqlite3
            tmp_path = BACKUPS_DIR / f"_tmp_validate_{int(time.time()*1000)}.sqlite"
            with tmp_path.open("wb") as out:
                buf_or_path.seek(0)
                shutil.copyfileobj(buf_or_path, out)
            buf_or_path.seek(0)

        if header != b"SQLite format 3\x00":
            if tmp_path.name.startswith("_tmp_validate_") and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            return False

        # tenta abrir e fazer integrity check
        ok = False
        try:
            with sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True) as conn:
                cur = conn.execute("PRAGMA integrity_check;")
                row = cur.fetchone()
                ok = (row and row[0] == "ok")
        finally:
            # limpar tmp se necessário
            if tmp_path.name.startswith("_tmp_validate_") and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        return ok
    except Exception:
        # limpeza de segurança
        try:
            if 'tmp_path' in locals() and tmp_path.name.startswith("_tmp_validate_") and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False

def make_timestamped_backup(src: Path) -> Path | None:
    if not src.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = BACKUPS_DIR / f"dados-{ts}.sqlite"
    shutil.copy2(src, dst)
    return dst

def read_file_bytes(p: Path) -> bytes:
    with p.open("rb") as f:
        return f.read()

# --------------------------------------------------
# Seção: Baixar Backup (local)
# --------------------------------------------------
st.header("⬇️ Baixar backup (local)")
if DB_PATH.exists():
    size = DB_PATH.stat().st_size
    mtime = datetime.fromtimestamp(DB_PATH.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
    st.caption(f"Arquivo: `{DB_PATH.name}` • {_fmt_bytes(size)} • Atualizado em {mtime}")
    st.download_button(
        label="Download do banco de dados",
        data=read_file_bytes(DB_PATH),
        file_name=f"{DB_PATH.name}",
        mime="application/octet-stream",
        type="primary",
        use_container_width=True,
    )
else:
    st.warning("Banco de dados não encontrado em `dados.db`.")

# (Opcional) Lista últimos backups locais já gerados
with st.expander("Backups locais (pasta ./backups)"):
    backups = sorted(BACKUPS_DIR.glob("dados-*.sqlite"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        st.write("_Nenhum backup encontrado._")
    else:
        for b in backups[:20]:
            st.write(f"- `{b.name}` • {_fmt_bytes(b.stat().st_size)} • {datetime.fromtimestamp(b.stat().st_mtime):%d/%m/%Y %H:%M}")
        st.info("Você pode copiar/guardar esses arquivos manualmente (ex.: em nuvem).")

st.divider()

# --------------------------------------------------
# Seção: Restaurar Backup
# --------------------------------------------------
st.header("⬆️ Restaurar backup")
st.markdown(
    "Envie um arquivo `.sqlite` ou `.db`. "
    "**Faremos um backup automático do banco atual antes de substituir.**"
)

uploaded = st.file_uploader("Escolha o arquivo de backup", type=["sqlite", "db"])
col_a, col_b = st.columns([1, 1], vertical_alignment="center")
with col_a:
    do_auto_backup = st.checkbox("Criar backup automático antes de restaurar", value=True)
with col_b:
    confirm = st.checkbox("Confirmo que desejo substituir o banco atual", value=False)

restore_btn = st.button("Restaurar agora", type="primary", use_container_width=True, disabled=not (uploaded and confirm))

if restore_btn and uploaded:
    # 1) validar arquivo
    if not is_sqlite_file(uploaded):
        st.error("Arquivo enviado não parece ser um banco SQLite válido (falha na assinatura ou no `PRAGMA integrity_check`).")
        st.stop()

    # 2) grava para um tmp
    tmp_incoming = BACKUPS_DIR / f"_incoming_{int(time.time()*1000)}.sqlite"
    with tmp_incoming.open("wb") as out:
        uploaded.seek(0)
        shutil.copyfileobj(uploaded, out)

    try:
        # 3) backup automático (opcional)
        backup_path = None
        if do_auto_backup and DB_PATH.exists():
            backup_path = make_timestamped_backup(DB_PATH)

        # 4) troca atômica
        #    - renomeia DB atual para .old (fallback extra) e move o novo para o lugar
        old_path = APP_DIR / "dados.old.sqlite"
        if old_path.exists():
            old_path.unlink(missing_ok=True)
        if DB_PATH.exists():
            os.replace(DB_PATH, old_path)
        os.replace(tmp_incoming, DB_PATH)  # coloca o novo no lugar

        # 5) sanity check final
        if not is_sqlite_file(DB_PATH):
            # rollback
            if DB_PATH.exists():
                DB_PATH.unlink(missing_ok=True)
            if old_path.exists():
                os.replace(old_path, DB_PATH)
            st.error("Falha na validação final do banco restaurado. O banco anterior foi recuperado.")
            st.stop()

        # tudo certo — removemos o .old
        if old_path.exists():
            old_path.unlink(missing_ok=True)

        msg = "Banco restaurado com sucesso."
        if backup_path:
            msg += f" Backup automático criado: `{backup_path.name}`."
        st.success(msg)
        st.toast("Pronto! Recarregue a página que usa o banco para ver os dados restaurados.", icon="✅")

    except Exception as e:
        # em caso de erro crítico, tentamos limpar tmp e restaurar .old
        if tmp_incoming.exists():
            tmp_incoming.unlink(missing_ok=True)
        st.exception(e)

# --------------------------------------------------
# (Futuro) Backup/restore na nuvem
# --------------------------------------------------
with st.expander("☁️ Integração com nuvem (em breve)"):
    st.markdown(
        "- **Upload** automático do backup mais recente para um bucket (Supabase Storage, S3, etc.).\n"
        "- **Download**/restauração direto da nuvem.\n"
        "- **Agendamentos** (ex.: diário) para criar backups incrementais.\n"
        "\n> Quando conectarmos, basta trocar as funções `make_timestamped_backup`/`read_file_bytes` por chamadas do provedor."
    )
