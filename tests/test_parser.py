from pathlib import Path

import pytest

from tramitacao import calcular_permanencias, ler_ficha, resumo_por_pessoa
from tramitacao.feriados import dias_nao_uteis, pascoa

PDF = Path(__file__).resolve().parents[2] / "2427-2026.pdf"
pytestmark = pytest.mark.skipif(not PDF.exists(), reason="PDF de exemplo ausente")


@pytest.fixture(scope="module")
def proc():
    return ler_ficha(PDF.read_bytes(), PDF.name)


def test_cabecalho(proc):
    assert proc.numero == "2427/2026"
    assert proc.assunto == "Licitação - Aditivo Prazo"
    assert proc.situacao == "Encaminhado"
    assert proc.impresso_em.strftime("%d/%m/%Y %H:%M:%S") == "16/09/2026 09:27:33"
    assert "micro recapeamento asfáltico" in proc.descricao


def test_ocorrencias(proc):
    oc = proc.ocorrencias
    assert oc["ocorrencia"].tolist() == list(range(1, 19))
    assert oc.loc[0, "para"] == "MARCO AURELIO BERTAN"
    assert oc.iloc[-1]["para"] == "VIVIANE ARROIO ORLANDO PEREIRA"
    assert oc.loc[oc.ocorrencia == 5, "confirmacao"].item() == "OK"
    assert "IPCA" in oc.iloc[-1]["descricao"]  # descrição multilinha


def test_permanencias(proc):
    fer = list(dias_nao_uteis([2026]))
    df = calcular_permanencias(proc.ocorrencias, proc.impresso_em, fer)
    assert df["dias_corridos"].sum() == pytest.approx(49.76, abs=0.01)
    r = resumo_por_pessoa(df).set_index("pessoa")
    assert r.loc["RAFAEL DE VASCONCELOS TAVEIRA", "dias_corridos"] == pytest.approx(15.28, abs=0.01)
    assert r.loc["MARCO AURELIO BERTAN", "dias_uteis"] == 11
    assert r.loc["VIVIANE ARROIO ORLANDO PEREIRA", "com_processo_agora"]
    assert r["percentual"].sum() == pytest.approx(100)


def test_pascoa():
    assert pascoa(2026).isoformat() == "2026-04-05"
    assert pascoa(2027).isoformat() == "2027-03-28"
