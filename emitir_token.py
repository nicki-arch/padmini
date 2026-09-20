"""
Emite um token de acesso ao relatório completo (para teste ou para o webhook).

Precisa de PADMINI_SECRET no ambiente.

Uso:
  python emitir_token.py mapa   DATA HORA LAT LON
  python emitir_token.py compat DATA_A HORA_A LAT_A LON_A DATA_B HORA_B LAT_B LON_B

Ex.: python emitir_token.py mapa 1990-09-15 14:30 -30.0346 -51.2177
"""
import sys
import acesso


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    produto = argv[1]
    args = argv[2:]
    if produto == "mapa":
        if len(args) != 4:
            print("mapa exige: DATA HORA LAT LON")
            return 1
        chave = acesso.chave_mapa(args[0], args[1], args[2], args[3])
    elif produto == "compat":
        if len(args) != 8:
            print("compat exige: DATA_A HORA_A LAT_A LON_A DATA_B HORA_B LAT_B LON_B")
            return 1
        chave = acesso.chave_compat(tuple(args[0:4]), tuple(args[4:8]))
    else:
        print("produto deve ser 'mapa' ou 'compat'")
        return 1
    print(acesso.emitir_token(produto, chave))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
