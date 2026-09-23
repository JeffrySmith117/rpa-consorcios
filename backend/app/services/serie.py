"""Série histórica: grava os valores tratados de cada trimestre consultado.

É chamada a cada consulta do RPA (o histórico cresce naturalmente com o uso)
e pelo "Carregar histórico" do dashboard."""
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import MetricaSerie
from app.services.tratamento import corrigir_unidades, normalizar, validar_registros


def salvar_serie(db: Session, data_base: str, registros: list[dict]) -> int:
    """Substitui os valores do trimestre pelos recém-tratados. Retorna quantos gravou."""
    metricas = validar_registros(registros, [])
    corrigir_unidades(metricas, [])
    linhas = []
    for mid, m in metricas.items():
        if normalizado := normalizar(m, []):
            valor, unidade = normalizado
            linhas.append(MetricaSerie(data_base=data_base, id_metrica=mid, nome=m.nome, valor=valor, unidade=unidade))
    if not linhas:
        return 0
    db.execute(delete(MetricaSerie).where(MetricaSerie.data_base == data_base))
    db.add_all(linhas)
    db.commit()
    return len(linhas)