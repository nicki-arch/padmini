

def test_textos_sem_erro_de_concordancia_nem_placeholder():
    """Parte 21: 'em relação a o Ascendente' e 'signo próprio (Áries ou Escorpião)'
    chegavam ao cliente. O texto tem de nomear o signo real e contrair a preposição."""
    from datetime import datetime
    from compute_chart import calcular_mapa
    from detectar_fatos import detectar_todos_os_fatos
    from montar_texto import montar_secoes
    casos = [(datetime(1990, 5, 15, 14, 30), -23.5505, -46.6333),
             (datetime(1985, 11, 3, 5, 10), -30.0346, -51.2177),
             (datetime(2001, 7, 22, 21, 40), -3.1190, -60.0217)]
    for dt, lat, lon in casos:
        mapa = calcular_mapa(dt_local_naive=dt, lat=lat, lon=lon)
        secoes, _ = montar_secoes(mapa, detectar_todos_os_fatos(mapa))
        for conteudo in secoes.values():
            for p in (conteudo if isinstance(conteudo, list) else [conteudo]):
                assert " a o " not in p and " a a " not in p, p
                assert " ou " not in p.split("dá")[0] or "signo próprio" not in p, p
                assert "{" not in p, p
