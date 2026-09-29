import csv
import json


def ler_catalogo(caminho) -> list:
    """Lê o arquivo CSV do catálogo e retorna seus registros."""

    with open(caminho, "r", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        registros = list(leitor)

    print(f"Fonte: catálogo.csv | Registros lidos: {len(registros)}")

    return registros


def ler_interacoes(caminho) -> list:
    """Lê o arquivo JSON de interações e retorna seus registros."""

    with open(caminho, "r", encoding="utf-8") as arquivo:
        registros = json.load(arquivo)

    print(f"Fonte: interacoes.json | Registros lidos: {len(registros)}")

    return registros


def ler_comentarios(caminho) -> list:
    """Lê o arquivo JSON de comentários e avaliações e retorna seus registros."""

    with open(caminho, "r", encoding="utf-8") as arquivo:
        registros = json.load(arquivo)

    print(f"Fonte: comentarios.json | Registros lidos: {len(registros)}")

    return registros


def ler_fontes(config) -> dict:
    """Lê todas as fontes configuradas e retorna os registros separados por origem."""

    catalogo = ler_catalogo(config["dados"]["catalogo"])
    interacoes = ler_interacoes(config["dados"]["interacoes"])
    comentarios = ler_comentarios(config["dados"]["comentarios"])

    return {
        "catalogo": catalogo,
        "interacoes": interacoes,
        "comentarios": comentarios
    }


def salvar_catalogo(registros: list, caminho) -> None:
    """Salva os registros tratados do catálogo em um arquivo CSV."""

    if not registros:
        return

    campos = registros[0].keys()

    with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(registros)


def salvar_json(registros: list, caminho) -> None:
    """Salva registros tratados em um arquivo JSON."""

    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(
            registros,
            arquivo,
            ensure_ascii=False,
            indent=4
        )