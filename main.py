# main.py  (launcher para o arquivo principal com nome em pt/emoji)
from pathlib import Path
import runpy

entry = Path(__file__).with_name("🏠_Início.py")
runpy.run_path(str(entry), run_name="__main__")