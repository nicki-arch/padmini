"""
Padmini — busca de cidades (local, sem API externa).

Fonte: GeoNames (cities1000 = cidades com mais de 1.000 habitantes),
licença CC BY 4.0 — exige crédito ao GeoNames no site.
Na primeira execução gera um índice compacto em data/cidades_index.tsv.
"""

import bisect
import csv
import unicodedata
from pathlib import Path

DATA = Path(__file__).parent / "data"
INDICE = DATA / "cidades_index.tsv"

PAIS_PT = {
    "BR": "Brasil", "PT": "Portugal", "US": "Estados Unidos", "AR": "Argentina", "UY": "Uruguai",
    "PY": "Paraguai", "CL": "Chile", "ES": "Espanha", "IT": "Itália", "DE": "Alemanha",
    "FR": "França", "GB": "Reino Unido", "JP": "Japão", "IN": "Índia", "CA": "Canadá",
    "MX": "México", "CO": "Colômbia", "PE": "Peru", "BO": "Bolívia", "AO": "Angola", "MZ": "Moçambique",
}


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().replace("-", " ").split())


def _latino(texto: str) -> bool:
    return all(c.isascii() and (c.isalpha() or c in " '.") for c in texto)


def construir_indice() -> None:
    paises = {}
    with open(DATA / "countryInfo.txt", encoding="utf-8") as f:
        for linha in f:
            if not linha.startswith("#"):
                p = linha.rstrip("\n").split("\t")
                paises[p[0]] = PAIS_PT.get(p[0], p[4])
    estados = {}
    with open(DATA / "admin1CodesASCII.txt", encoding="utf-8") as f:
        for linha in f:
            codigo, nome, *_ = linha.rstrip("\n").split("\t")
            estados[codigo] = nome

    with open(DATA / "cities1000.txt", encoding="utf-8") as f, open(INDICE, "w", encoding="utf-8", newline="") as out:
        w = csv.writer(out, delimiter="\t")
        for linha in f:
            c = linha.rstrip("\n").split("\t")
            nome, ascii_, alternativos = c[1], c[2], c[3]
            lat, lon, pais, admin1, pop, fuso = c[4], c[5], c[8], c[10], int(c[14] or 0), c[17]
            rotulo = ", ".join(x for x in [nome, estados.get(f"{pais}.{admin1}", ""), paises.get(pais, pais)] if x)
            chaves = {normalizar(nome), normalizar(ascii_)}
            if pop >= 100_000:  # nomes alternativos só para cidades grandes (ex.: "Lisboa" -> Lisbon)
                chaves |= {normalizar(a) for a in alternativos.split(",") if a and _latino(a)}
            for chave in chaves:
                if chave:
                    w.writerow([chave, rotulo, lat, lon, pop, fuso])


class BuscaCidades:
    def __init__(self) -> None:
        if not INDICE.exists():
            construir_indice()
        linhas = []
        with open(INDICE, encoding="utf-8") as f:
            for chave, rotulo, lat, lon, pop, fuso in csv.reader(f, delimiter="\t"):
                linhas.append((chave, rotulo, float(lat), float(lon), int(pop), fuso))
        linhas.sort(key=lambda x: x[0])
        self._linhas = linhas
        self._chaves = [x[0] for x in linhas]

    def buscar(self, consulta: str, limite: int = 8) -> list[dict]:
        q = normalizar(consulta)
        if len(q) < 2:
            return []
        i = bisect.bisect_left(self._chaves, q)
        achados = {}
        while i < len(self._chaves) and self._chaves[i].startswith(q):
            chave, rotulo, lat, lon, pop, fuso = self._linhas[i]
            exato = chave == q
            atual = achados.get(rotulo)
            if atual is None or (exato and not atual["_exato"]):
                achados[rotulo] = {"rotulo": rotulo, "lat": lat, "lon": lon, "fuso": fuso,
                                   "_pop": pop, "_exato": exato}
            i += 1
        ordenados = sorted(achados.values(), key=lambda x: (not x["_exato"], -x["_pop"]))
        return [{k: v for k, v in x.items() if not k.startswith("_")} for x in ordenados[:limite]]


if __name__ == "__main__":
    import time
    t = time.time()
    busca = BuscaCidades()
    print(f"índice carregado em {time.time() - t:.1f}s ({len(busca._chaves)} chaves)")
    for termo in ["porto alegre", "sao jose", "lisboa", "rio", "santa cruz do sul", "nova york"]:
        t = time.time()
        r = busca.buscar(termo, 4)
        print(f"\n{termo!r} ({(time.time() - t) * 1000:.1f} ms)")
        for c in r:
            print("  ", c["rotulo"], c["lat"], c["lon"])
