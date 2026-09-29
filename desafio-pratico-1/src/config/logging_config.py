import logging
import os
import time
from contextlib import contextmanager


def configurar_logging() -> None:
    """Configura o registro de logs da aplicação."""

    os.makedirs("logs", exist_ok=True)

    logging.basicConfig(
        filename="logs/processamento.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        encoding="utf-8"
    )


@contextmanager
def registrar_etapa(nome: str):
    """Registra início, término, duração e falha de uma etapa do pipeline."""

    logger = logging.getLogger("src.etapas")

    inicio = time.time()
    logger.info("Etapa iniciada: %s", nome)

    try:
        yield

    except Exception:
        logger.exception(
            "Etapa com falha: %s (após %.4f segundos)",
            nome,
            time.time() - inicio
        )
        raise

    logger.info(
        "Etapa concluída: %s (%.4f segundos)",
        nome,
        time.time() - inicio
    )
