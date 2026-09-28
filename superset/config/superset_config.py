"""Configuração do Apache Superset do Desafio 2 (RF17, RF18).

Os segredos vêm do ambiente (superset/.env, fora do repositório).
"""

import os

from celery.schedules import crontab

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://superset:{os.environ['SUPERSET_META_SENHA']}@superset-db:5432/superset"
)

# Idiomas: o Superset escolhe o idioma pelo navegador (pt-BR). Todo idioma
# que o navegador pode pedir precisa estar em LANGUAGES; caso contrário o
# frontend não encontra a bandeira do idioma e a página fica preta. A imagem
# "lean" não traz as traduções compiladas, então a interface aparece em inglês;
# títulos, gráficos e textos do dashboard estão em português.
BABEL_DEFAULT_LOCALE = "en"
LANGUAGES = {
    "en": {"flag": "us", "name": "English"},
    "pt_BR": {"flag": "br", "name": "Brazilian Portuguese"},
}

FEATURE_FLAGS = {
    "ALERT_REPORTS": True,
    "DASHBOARD_CROSS_FILTERS": True,
}

# Celery: executa as consultas dos alertas e o agendador de relatórios.
REDIS_URL = "redis://redis:6379"


class CeleryConfig:
    broker_url = f"{REDIS_URL}/0"
    result_backend = f"{REDIS_URL}/1"
    imports = ("superset.sql_lab", "superset.tasks.scheduler")
    worker_prefetch_multiplier = 1
    task_acks_late = False
    beat_schedule = {
        "reports.scheduler": {"task": "reports.scheduler", "schedule": crontab(minute="*", hour="*")},
        "reports.prune_log": {"task": "reports.prune_log", "schedule": crontab(minute=0, hour=0)},
    }


CELERY_CONFIG = CeleryConfig

# Alertas: e-mail enviado ao Mailpit (servidor SMTP de teste, http://localhost:8025).
ALERT_REPORTS_NOTIFICATION_DRY_RUN = False
SMTP_HOST = "mailpit"
SMTP_PORT = 1025
SMTP_STARTTLS = False
SMTP_SSL = False
SMTP_USER = ""
SMTP_PASSWORD = ""
SMTP_MAIL_FROM = "alertas@plataforma-educacional.example"

# Endereço interno usado pelo worker para obter os dados do gráfico do alerta.
WEBDRIVER_BASEURL = "http://superset:8088/"
WEBDRIVER_BASEURL_USER_FRIENDLY = "http://localhost:8088/"
