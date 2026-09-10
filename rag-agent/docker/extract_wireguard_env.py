"""Converte um arquivo .conf nativo do WireGuard (ex: exportado da ProtonVPN)
para as variáveis de ambiente que o Gluetun espera no .env real.

Uso:
    python extract_wireguard_env.py /caminho/para/seu-perfil.conf

O .conf NUNCA deve ser commitado nem colocado dentro deste repositório — passe
o caminho de onde ele estiver guardado localmente. A saída deste script deve
ser colada no seu .env real (também nunca commitado), não no .env.example.
"""
import configparser
import sys


def extract(conf_path: str) -> dict[str, str]:
    parser = configparser.ConfigParser(strict=False)
    parser.read(conf_path)

    private_key = parser.get("Interface", "PrivateKey", fallback=None)
    addresses = parser.get("Interface", "Address", fallback=None)

    if not private_key or not addresses:
        raise ValueError(
            "Não encontrei PrivateKey/Address na seção [Interface] do arquivo. "
            "Confirme que é um .conf WireGuard válido."
        )

    return {
        "WIREGUARD_PRIVATE_KEY": private_key.strip(),
        "WIREGUARD_ADDRESSES": addresses.strip(),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python extract_wireguard_env.py <caminho_para_arquivo.conf>")
        sys.exit(1)

    env_vars = extract(sys.argv[1])
    print("# Cole estas linhas no seu .env real (nunca no .env.example nem no repositório):")
    for key, value in env_vars.items():
        print(f"{key}={value}")
