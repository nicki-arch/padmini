"""Baixa os dados de cidades do GeoNames (rodar uma vez antes de subir o servidor)."""

import io
import urllib.request
import zipfile
from pathlib import Path

DATA = Path(__file__).parent / "data"
BASE = "https://download.geonames.org/export/dump/"


def baixar(nome: str) -> bytes:
    print(f"baixando {nome}...")
    with urllib.request.urlopen(BASE + nome, timeout=120) as r:
        return r.read()


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(baixar("cities1000.zip"))) as z:
        z.extract("cities1000.txt", DATA)
    for nome in ["admin1CodesASCII.txt", "countryInfo.txt"]:
        (DATA / nome).write_bytes(baixar(nome))
    indice = DATA / "cidades_index.tsv"
    if indice.exists():
        indice.unlink()
    from cidades import BuscaCidades
    BuscaCidades()
    print("pronto")
