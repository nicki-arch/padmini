"""
Rodada 19.1 (18/out/2026): a foto da Dona Valderez nos arcos do site e o Instagram fora do ar.

  - A foto entra por `marca.retrato(vaga, …)`: com o arquivo da vaga, a <img class="foto-real">;
    sem ele, a roda de sempre (nunca imagem quebrada). Os templates nunca apontam o arquivo.
  - Rede com `ativa: false` no marca.yaml some de todo o site (rodapé, "quem revisa",
    /links, sameAs). O Instagram fica assim até o perfil abrir sem login.
"""
import importlib.util
import json
import re

import pytest

from test_app import RAIZ, app_mod, cliente  # primeiro: define os segredos de teste
import enderecos
import ilustracoes
import marca
import pagina_links

HTML = {"accept": "text/html"}
# o catálogo como está no ar (as páginas de produto em breve usam o produto.html)
pytestmark = pytest.mark.catalogo_real
FOTOS = ("foto-valderez", "foto-valderez-rosto")
# página → (vaga, alt) de cada arco onde a foto entra
LUGARES = {
    "/": [("foto-valderez-rosto", ""), ("foto-valderez", "Dona Valderez")],
    "/leituras": [("foto-valderez", "Dona Valderez")],
    "/tarot": [("foto-valderez", "Dona Valderez")],
    "/mapa": [("foto-valderez-rosto", "")],
    "/seu-ano?previa=chave-previa-teste": [("foto-valderez-rosto", "")],
    "/lista": [("foto-valderez-rosto", "")],
    "/links": [("foto-valderez-rosto", "")],
}


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    for v in ("PADMINI_CAPTURA", "PADMINI_VENDAS_TESTE", "PADMINI_DOMINIO_PRINCIPAL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("PADMINI_PREVIA_CHAVE", "chave-previa-teste")
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


def _com_fotos(monkeypatch, tem: bool):
    """Simula as fotos presentes (ou ausentes) sem depender dos arquivos no checkout."""
    original = ilustracoes.url

    def url(vaga):
        if vaga in FOTOS:
            return f"/static/ilustracoes/aquarela-2026/{vaga}.webp" if tem else ""
        return original(vaga)
    monkeypatch.setattr(ilustracoes, "url", url)
    app_mod._paginas_prontas.clear()


def _pagina(rota):
    r = cliente.get(rota, headers=HTML)
    assert r.status_code == 200, (rota, r.status_code)
    return r.text


# ------------------------------------------------------------------ a foto
def test_vagas_no_manifesto():
    assert ilustracoes.VAGAS["foto-valderez"]["proporcao"] == [3, 4]
    assert ilustracoes.VAGAS["foto-valderez"]["minimo"] == [900, 1200]
    assert ilustracoes.VAGAS["foto-valderez-rosto"]["proporcao"] == [4, 5]
    assert ilustracoes.VAGAS["foto-valderez-rosto"]["minimo"] == [560, 700]
    assert pagina_links.VAGA_FOTO == "foto-valderez-rosto"


def test_retrato_com_e_sem_arquivo(monkeypatch):
    _com_fotos(monkeypatch, True)
    tag = marca.retrato("foto-valderez", 420, 560, alt="Dona Valderez")
    assert 'class="foto-real"' in tag and 'alt="Dona Valderez"' in tag and "aria-hidden" not in tag
    assert 'width="420" height="560"' in tag and 'loading="lazy"' in tag and 'decoding="async"' in tag
    assert 'aria-hidden="true"' in marca.retrato("foto-valderez-rosto", 60, 75)  # decorativa
    _com_fotos(monkeypatch, False)
    assert marca.retrato("foto-valderez", 420, 560, roda_tamanho=200, clara=True) == marca.roda(200, clara=True)


def test_retrato_de_vaga_inexistente_e_erro():
    with pytest.raises(KeyError):
        marca.retrato("foto-quem-nao-existe", 10, 10)


@pytest.mark.parametrize("rota", list(LUGARES))
def test_foto_nos_arcos(ocidental, monkeypatch, rota):
    _com_fotos(monkeypatch, True)
    html = _pagina(rota)
    for vaga, alt in LUGARES[rota]:
        tag = re.search(rf'<img class="foto-real" src="/static/ilustracoes/aquarela-2026/{vaga}\.webp"[^>]*>', html)
        assert tag, (rota, vaga)
        assert f'alt="{alt}"' in tag.group(0), (rota, vaga, tag.group(0))


def test_selo_do_topo_da_home_nao_espera_rolar(ocidental, monkeypatch):
    _com_fotos(monkeypatch, True)
    html = _pagina("/")
    topo = re.search(r'<img class="foto-real"[^>]*foto-valderez-rosto[^>]*>', html).group(0)
    assert 'loading="eager"' in topo
    grande = re.search(r'<img class="foto-real"[^>]*foto-valderez\.webp[^>]*>', html).group(0)
    assert 'loading="lazy"' in grande


@pytest.mark.parametrize("rota", list(LUGARES))
def test_sem_arquivo_volta_a_roda(ocidental, monkeypatch, rota):
    _com_fotos(monkeypatch, False)
    html = _pagina(rota)
    assert "foto-real" not in html and "foto-valderez" not in html
    assert "/static/valderez/roda" in html


def test_o_arco_grande_com_a_foto_nao_fica_escondido_do_leitor_de_tela(ocidental, monkeypatch):
    _com_fotos(monkeypatch, True)
    html = _pagina("/")
    assert '<div class="arco foto-grande">' in html


def test_templates_nunca_apontam_o_arquivo_da_foto():
    for arq in (RAIZ / "static" / "ocidental").glob("*.html"):
        texto = arq.read_text(encoding="utf-8")
        assert "/static/ilustracoes/" not in texto, arq
        fora_do_retrato = re.sub(r"marca\.retrato\([^)]*\)", "", texto)
        assert "foto-valderez" not in fora_do_retrato, arq


def test_css_da_foto_ocupa_o_arco():
    css = (RAIZ / "static" / "valderez" / "v2.css").read_text(encoding="utf-8")
    regra = re.search(r"[^}]*\.foto-real\s*\{([^}]*)\}", css).group(1)
    for decl in ("width: 100%", "height: 100%", "object-fit: cover", "object-position: 50% 10%", "opacity: 1"):
        assert decl in regra


def _checar():
    spec = importlib.util.spec_from_file_location("checar", RAIZ / "scripts" / "checar_ilustracoes.py")
    checar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checar)
    return checar


def test_checar_aceita_foto_que_falta_mas_confere_a_que_existe(tmp_path, monkeypatch):
    from PIL import Image
    checar = _checar()
    monkeypatch.setattr(ilustracoes, "PASTA", tmp_path)
    (tmp_path / "x").mkdir()
    monkeypatch.setattr(ilustracoes, "VAGAS", {k: ilustracoes.VAGAS[k] for k in FOTOS})
    assert checar.conferir("x") == []  # nenhuma das duas: a roda no lugar, sem erro
    Image.new("RGB", (500, 500)).save(tmp_path / "x" / "foto-valderez-rosto.webp", "WEBP")
    erros = checar.conferir("x")
    assert any("proporção 4:5" in e for e in erros) and any("mínimo 560×700" in e for e in erros)


def test_original_nao_vai_para_o_repositorio():
    import subprocess
    versionados = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True).stdout
    assert "foto-valderez-original" not in versionados and "_material/" not in versionados


# ------------------------------------------------------------------ o Instagram
def test_ativas_filtra_e_o_padrao_e_ligada():
    redes = [{"nome": "A"}, {"nome": "B", "ativa": False}, {"nome": "C", "ativa": True}]
    assert [r["nome"] for r in enderecos.ativas(redes)] == ["A", "C"]


def test_instagram_desligado_no_marca_yaml():
    insta = next(r for r in enderecos.TODAS_AS_REDES if r["nome"] == "Instagram")
    assert insta["ativa"] is False
    assert [r["nome"] for r in enderecos.REDES] == ["TikTok", "YouTube"]


@pytest.mark.parametrize("rota", ["/", "/mapa", "/links", "/leituras", "/termos", "/tarot"])
def test_rede_inativa_nao_aparece_em_lugar_nenhum(ocidental, rota):
    html = _pagina(rota)
    assert "instagram.com" not in html, rota
    assert "tiktok.com/@astrologiavalderez" in html and "youtube.com/@astrologiavalderez" in html, rota


def test_rede_inativa_fora_do_same_as(ocidental):
    html = _pagina("/")
    bloco = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
    org = next(g for g in json.loads(bloco)["@graph"] if g["@type"] == "Organization")
    assert org["sameAs"] == [r["url"] for r in enderecos.REDES]
    assert not any("instagram" in u for u in org["sameAs"])


def test_ativa_precisa_ser_booleano(monkeypatch, tmp_path):
    import importlib
    import yaml
    original = (RAIZ / "conteudo" / "ocidental" / "marca.yaml").read_text(encoding="utf-8")
    dados = yaml.safe_load(original)
    dados["redes"][0]["ativa"] = "não"
    texto = yaml.safe_dump(dados, allow_unicode=True)
    real = type(RAIZ).read_text

    def ler(self, *a, **k):
        return texto if self.name == "marca.yaml" else real(self, *a, **k)
    monkeypatch.setattr(type(RAIZ), "read_text", ler)
    with pytest.raises(ValueError, match="ativa"):
        importlib.reload(enderecos)
    monkeypatch.undo()
    importlib.reload(enderecos)


def test_fotos_entregues_no_conjunto_ativo():
    """As duas fotos de 18/out estão no conjunto ativo, dentro do limite de peso
    (o checar_ilustracoes confere proporção e mínimo no test_rodada9_fase_b)."""
    for vaga in FOTOS:
        arq = ilustracoes.caminho(vaga)
        assert arq is not None and arq.stat().st_size < 300 * 1024, vaga
