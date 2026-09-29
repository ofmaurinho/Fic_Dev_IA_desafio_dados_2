from datetime import datetime

import numpy as np
import pytest

from src.banco.postgresql import (
    inserir_categorias,
    inserir_conteudos,
    inserir_interacoes,
    inserir_usuarios,
    obter_categorias
)
from src.banco.vetorial import (
    buscar_similares,
    conectar_vetorial,
    obter_embeddings_existentes,
    salvar_embedding,
    sincronizar_embeddings
)
from src.recomendacao.motor import (
    calcular_candidatos,
    inserir_recomendacoes,
    obter_recomendacoes_usuario
)


DIMENSAO = 512


@pytest.fixture
def config():
    return {
        "postgresql": {
            "host": "localhost",
            "porta": 5433,
            "banco": "desafio_dados",
            "usuario": "postgres"
        }
    }


@pytest.fixture
def conexao(config):
    conexao = conectar_vetorial(config)

    yield conexao

    conexao.rollback()
    conexao.close()


def vetor_unitario(indices: list[int]) -> np.ndarray:
    vetor = np.zeros(DIMENSAO, dtype=np.float32)
    vetor[indices] = 1.0

    return vetor / np.linalg.norm(vetor)


def criar_conteudos_teste(conexao, ids: list[int]) -> None:
    inserir_categorias(conexao, [{"categoria": "Teste Vetorial"}])

    inserir_conteudos(
        conexao,
        [
            {
                "conteudo_id": conteudo_id,
                "titulo": f"Conteúdo vetorial {conteudo_id}",
                "tipo": "Curso",
                "categoria": "Teste Vetorial",
                "nivel": "Básico",
                "carga_horaria_min": 10,
                "data_publicacao": "2026-01-01",
                "descricao": "Descrição de teste",
                "autor": "Autor de teste"
            }
            for conteudo_id in ids
        ],
        obter_categorias(conexao)
    )


def test_salvar_e_buscar_embedding(conexao):
    criar_conteudos_teste(conexao, [999990, 999991])

    salvar_embedding(conexao, 999990, vetor_unitario([0, 1]), "teste", "a" * 64)
    salvar_embedding(conexao, 999991, vetor_unitario([2, 3]), "teste", "b" * 64)

    existentes = obter_embeddings_existentes(conexao)

    assert existentes[999990] == ("teste", "a" * 64)

    resultados = buscar_similares(conexao, vetor_unitario([0, 1]), 1)

    assert resultados[0]["conteudo_id"] == 999990
    assert resultados[0]["posicao"] == 1
    assert resultados[0]["categoria"] == "Teste Vetorial"
    assert resultados[0]["similaridade"] == pytest.approx(1.0, abs=1e-5)


def test_salvar_embedding_atualiza_existente(conexao):
    criar_conteudos_teste(conexao, [999992])

    salvar_embedding(conexao, 999992, vetor_unitario([0]), "teste", "a" * 64)
    salvar_embedding(conexao, 999992, vetor_unitario([1]), "teste-v2", "c" * 64)

    assert obter_embeddings_existentes(conexao)[999992] == ("teste-v2", "c" * 64)


def test_calcular_candidatos_aplica_indices_e_conclusao(conexao):
    criar_conteudos_teste(conexao, [999993, 999994, 999995])

    salvar_embedding(conexao, 999993, vetor_unitario([10]), "teste", "a" * 64)
    salvar_embedding(conexao, 999994, vetor_unitario([10, 11]), "teste", "b" * 64)
    salvar_embedding(conexao, 999995, vetor_unitario([20]), "teste", "c" * 64)

    inserir_usuarios(conexao, [{"usuario_id": 999996}])

    inserir_interacoes(
        conexao,
        [
            {
                "usuario_id": 999996,
                "conteudo_id": 999993,
                "tipo_interacao": "visualização",
                "data_hora": "2026-01-01T10:00:00",
                "tempo_consumido": 10,
                "percentual_conclusao": 40,
                "avaliacao_atribuida": None
            },
            {
                "usuario_id": 999996,
                "conteudo_id": 999995,
                "tipo_interacao": "conclusão",
                "data_hora": "2026-01-02T10:00:00",
                "tempo_consumido": 10,
                "percentual_conclusao": 100,
                "avaliacao_atribuida": None
            }
        ]
    )

    parametros = {
        "tipos_visualizacao": ["visualização", "início", "conclusão"],
        "tipo_curtida": "curtida",
        "tipo_conclusao": "conclusão",
        "nota_minima_curtida": 4,
        "limiar_positivo": 70,
        "limiar_negativo": 40,
        "normalizar_indices": False
    }

    candidatos = {
        candidato["conteudo_id"]: candidato
        for candidato in calcular_candidatos(
            conexao, 999996, {999994}, parametros
        )
    }

    # Perfil de visualização = média de e10 (visualização) e e20 (conclusão).
    # Perfil de curtidas = e10+e11 (conteúdo bem avaliado no MongoDB).

    assert candidatos[999995]["i_conc"] == 0
    assert candidatos[999995]["pontuacao"] == 0
    assert candidatos[999995]["status"] == "Negativo"

    assert candidatos[999993]["i_vis"] == pytest.approx(0.7071, abs=1e-3)
    assert candidatos[999993]["i_cur"] == pytest.approx(0.7071, abs=1e-3)
    assert candidatos[999993]["pontuacao"] == pytest.approx(70.71, abs=0.05)
    assert candidatos[999993]["status"] == "Positivo"

    assert candidatos[999994]["i_vis"] == pytest.approx(0.5, abs=1e-3)
    assert candidatos[999994]["i_cur"] == pytest.approx(1.0, abs=1e-3)
    assert candidatos[999994]["pontuacao"] == pytest.approx(75.0, abs=0.05)


def conteudo_teste(conteudo_id: int, titulo: str) -> dict:
    return {
        "conteudo_id": conteudo_id,
        "titulo": titulo,
        "descricao": "Descrição de teste"
    }


def test_sincronizar_gera_e_reaproveita(conexao):
    criar_conteudos_teste(conexao, [999986, 999987])

    conteudos = [
        conteudo_teste(999986, "Primeiro"),
        conteudo_teste(999987, "Segundo")
    ]

    lotes = []

    def gerador_falso(textos):
        lotes.append(len(textos))
        return np.array([vetor_unitario([i]) for i in range(len(textos))])

    primeira = sincronizar_embeddings(conexao, conteudos, gerador_falso, "falso")
    segunda = sincronizar_embeddings(conexao, conteudos, gerador_falso, "falso")

    assert primeira == {"gerados": 2, "reaproveitados": 0, "falhas": 0}
    assert segunda["gerados"] == 0
    assert segunda["reaproveitados"] == 2
    assert lotes == [2]


def test_sincronizar_regenera_quando_modelo_muda(conexao):
    criar_conteudos_teste(conexao, [999988])

    salvar_embedding(conexao, 999988, vetor_unitario([0]), "antigo", "a" * 64)

    contagem = sincronizar_embeddings(
        conexao,
        [conteudo_teste(999988, "Texto")],
        lambda textos: np.array([vetor_unitario([5]) for _ in textos]),
        "novo"
    )

    assert contagem["gerados"] == 1
    assert obter_embeddings_existentes(conexao)[999988][0] == "novo"


def test_sincronizar_remove_embedding_quando_vetor_nulo(conexao):
    criar_conteudos_teste(conexao, [999997])

    salvar_embedding(conexao, 999997, vetor_unitario([0]), "antigo", "a" * 64)

    contagem = sincronizar_embeddings(
        conexao,
        [conteudo_teste(999997, "Texto novo")],
        lambda textos: np.zeros((len(textos), DIMENSAO), dtype=np.float32),
        "novo"
    )

    assert contagem == {"gerados": 0, "reaproveitados": 0, "falhas": 1}
    assert 999997 not in obter_embeddings_existentes(conexao)


def test_sincronizar_conta_falha_quando_modelo_gera_erro(conexao):
    criar_conteudos_teste(conexao, [999985])

    salvar_embedding(conexao, 999985, vetor_unitario([0]), "antigo", "a" * 64)

    def gerador_com_erro(textos):
        raise RuntimeError("falha simulada do modelo")

    contagem = sincronizar_embeddings(
        conexao,
        [conteudo_teste(999985, "Texto novo")],
        gerador_com_erro,
        "novo"
    )

    assert contagem == {"gerados": 0, "reaproveitados": 0, "falhas": 1}
    assert 999985 not in obter_embeddings_existentes(conexao)


def test_recomendacoes_do_usuario_usam_execucao_mais_recente(conexao):
    criar_conteudos_teste(conexao, [999998])
    inserir_usuarios(conexao, [{"usuario_id": 999998}, {"usuario_id": 999999}])

    def recomendacao(usuario_id):
        return {
            "usuario_id": usuario_id,
            "conteudo_id": 999998,
            "pontuacao": 80.0,
            "posicao": 1,
            "i_vis": 0.8,
            "i_cur": 0.8,
            "i_conc": 1,
            "status": "Positivo"
        }

    inserir_recomendacoes(conexao, [recomendacao(999998)], datetime(2999, 1, 1))
    inserir_recomendacoes(conexao, [recomendacao(999999)], datetime(2999, 1, 2))

    assert obter_recomendacoes_usuario(conexao, 999998) == []
    assert len(obter_recomendacoes_usuario(conexao, 999999)) == 1
