import numpy as np
import pytest

from src.embeddings.gerador import (
    calcular_hash_texto,
    carregar_modelo,
    gerar_embedding,
    gerar_embeddings_textos,
    preparar_texto,
    validar_dimensao
)


MODELO = "clip-ViT-B-32"
DIMENSAO = 512


@pytest.fixture(scope="module")
def modelo():
    return carregar_modelo(MODELO)


def similaridade(vetor_1: np.ndarray, vetor_2: np.ndarray) -> float:
    return float(vetor_1 @ vetor_2)


def test_preparar_texto_une_titulo_e_descricao():
    texto = preparar_texto("  Título  ", " Descrição   com   espaços ")

    assert texto == "Título. Descrição com espaços"


def test_calcular_hash_texto_deterministico():
    assert calcular_hash_texto("abc") == calcular_hash_texto("abc")
    assert calcular_hash_texto("abc") != calcular_hash_texto("abd")
    assert len(calcular_hash_texto("abc")) == 64


def test_carregar_modelo_reutiliza_instancia(modelo):
    assert carregar_modelo(MODELO) is modelo


def test_validar_dimensao(modelo):
    validar_dimensao(modelo, DIMENSAO)

    with pytest.raises(ValueError):
        validar_dimensao(modelo, 384)


def test_gerar_embedding_dimensao_norma_e_determinismo(modelo):
    vetor_1 = gerar_embedding(modelo, "Fundamentos de banco de dados")
    vetor_2 = gerar_embedding(modelo, "Fundamentos de banco de dados")

    assert vetor_1.shape == (DIMENSAO,)
    assert np.isclose(np.linalg.norm(vetor_1), 1.0, atol=1e-5)
    assert np.allclose(vetor_1, vetor_2, atol=1e-5)


def test_gerar_embeddings_em_lote(modelo):
    vetores = gerar_embeddings_textos(
        modelo,
        ["Curso de SQL", "Podcast sobre nuvem", "Vídeo sobre Python"],
        2
    )

    assert vetores.shape == (3, DIMENSAO)


def test_texto_longo_nao_gera_erro(modelo):
    texto_longo = " ".join(["Descrição extensa de um curso de dados."] * 60)

    vetor = gerar_embedding(modelo, texto_longo)

    assert vetor.shape == (DIMENSAO,)
    assert np.any(vetor)


def test_textos_relacionados_sao_mais_similares(modelo):
    consulta = gerar_embedding(modelo, "database SQL tables")
    relacionado = gerar_embedding(modelo, "relational database with PostgreSQL")
    nao_relacionado = gerar_embedding(modelo, "chocolate cake recipe")

    assert similaridade(consulta, relacionado) > similaridade(
        consulta, nao_relacionado
    )
