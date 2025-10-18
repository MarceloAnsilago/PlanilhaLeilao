# fix_encoding.py - converte .py com mojibake (cp1252/latin1) para UTF-8
import os, shutil

FILES = [
    "Inicio.py",
    "pages/1_Lotes.py",
    "pages/2_Criar_Lote.py",
    "pages/4_Editar.py",
    "pages/5_Imprimir.py",
    "pages/6_Animais_Fora.py",
    "pages/7_Duplicatas.py",
    "pages/8_Dados.py",
    "pages/9_Backup.py",
]

def looks_mojibake(text: str) -> bool:
    return ("Ã" in text) or ("Â" in text) or ("ð" in text)

def fix_file(path: str) -> bool:
    raw = open(path, "rb").read()
    try:
        text = raw.decode("utf-8")
        if not looks_mojibake(text):
            return False
        # reinterpreta como latin1 e volta para utf-8
        text = raw.decode("latin1", errors="ignore")
        text = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
    except UnicodeDecodeError:
        text = raw.decode("latin1", errors="ignore")
        text = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")

    # backup
    try:
        shutil.copy2(path, path + ".bak_encoding")
    except Exception:
        pass

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return True

changed = 0
for f in FILES:
    if os.path.exists(f):
        if fix_file(f):
            print("OK corrigido:", f)
            changed += 1
    else:
        print("ignorado (nao existe):", f)

print("\nFeito. Arquivos corrigidos:", changed)
