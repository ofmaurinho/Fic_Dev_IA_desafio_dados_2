import pytest

from src.main import ler_argumentos
from src.recomendacao.busca import buscar_conteudos


def test_sem_argumentos_executa_pipeline():
    argumentos = ler_argumentos([])

    assert argumentos.consulta is None
    assert argumentos.usuario is None
    assert argumentos.top_k is None


def test_consulta_com_top_k():
    argumentos = ler_argumentos(["--consulta", "banco de dados", "--top-k", "3"])

    assert argumentos.consulta == "banco de dados"
    assert argumentos.top_k == 3


@pytest.mark.parametrize(
    "argv",
    [
        ["--consulta", ""],
        ["--consulta", "   "],
        ["--top-k", "5"],
        ["--consulta", "dados", "--top-k", "0"],
        ["--consulta", "dados", "--top-k", "-1"],
        ["--consulta", "dados", "--usuario", "3"]
    ]
)
def test_argumentos_invalidos_encerram_com_erro(argv):
    with pytest.raises(SystemExit) as erro:
        ler_argumentos(argv)

    assert erro.value.code == 2


@pytest.mark.parametrize("quantidade", [0, -1])
def test_busca_rejeita_quantidade_nao_positiva(quantidade):
    config = {"embeddings": {}, "busca": {"top_k": 5}}

    with pytest.raises(ValueError):
        buscar_conteudos(config, "banco de dados", quantidade)
