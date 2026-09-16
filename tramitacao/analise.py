"""Cálculo de permanência (tempo parado) por ocorrência, pessoa e fase."""
from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd

UM_DIA = np.timedelta64(1, "D")


def dias_uteis(inicio: pd.Series, fim: pd.Series, feriados: list[date]) -> np.ndarray:
    """Contagem no padrão do art. 183 da Lei 14.133/2021: exclui o dia do início e inclui o do fim."""
    ini = inicio.values.astype("datetime64[D]") + UM_DIA
    end = fim.values.astype("datetime64[D]") + UM_DIA
    return np.busday_count(ini, np.maximum(ini, end), holidays=np.array(feriados, dtype="datetime64[D]"))


def calcular_permanencias(oc: pd.DataFrame, corte: datetime, feriados: list[date]) -> pd.DataFrame:
    """Cada ocorrência deixa o processo com o destinatário ('para') até a ocorrência seguinte.
    A última é contada até `corte` (data de impressão do relatório ou agora)."""
    df = oc.sort_values(["processo", "data", "ocorrencia"]).copy()
    df["saida"] = df.groupby("processo")["data"].shift(-1)
    df["em_andamento"] = df["saida"].isna()
    df["saida"] = df["saida"].fillna(pd.Timestamp(corte))
    df["saida"] = df[["saida", "data"]].max(axis=1)  # corte anterior à última ocorrência
    df["dias_corridos"] = (df["saida"] - df["data"]).dt.total_seconds() / 86400
    df["dias_uteis"] = dias_uteis(df["data"], df["saida"], feriados)
    prev_fim = df["previsao"] + pd.Timedelta(days=1)  # previsão vale até o fim do dia
    df["atraso_dias"] = ((df["saida"] - prev_fim).dt.total_seconds() / 86400).clip(lower=0)
    df.loc[df["previsao"].isna(), "atraso_dias"] = np.nan
    df["no_prazo"] = np.where(df["previsao"].isna(), None, df["atraso_dias"] <= 0)
    return df.reset_index(drop=True)


def _resumo(df: pd.DataFrame, chave: str | list[str]) -> pd.DataFrame:
    g = (df.groupby(chave, dropna=False)
           .agg(dias_corridos=("dias_corridos", "sum"),
                dias_uteis=("dias_uteis", "sum"),
                passagens=("ocorrencia", "count"),
                maior_permanencia=("dias_corridos", "max"),
                media_permanencia=("dias_corridos", "mean"),
                etapas_atrasadas=("atraso_dias", lambda s: int((s > 0).sum())),
                atraso_total=("atraso_dias", "sum"),
                com_processo_agora=("em_andamento", "any"))
           .reset_index())
    total = g["dias_corridos"].sum()
    g["percentual"] = g["dias_corridos"] / total * 100 if total else 0.0
    return g.sort_values("dias_corridos", ascending=False, ignore_index=True)


def resumo_por_pessoa(df: pd.DataFrame) -> pd.DataFrame:
    return _resumo(df, "para").rename(columns={"para": "pessoa"})


def resumo_por_fase(df: pd.DataFrame) -> pd.DataFrame:
    return _resumo(df, "fase_etapa")


def arredondar(df: pd.DataFrame, casas: int = 2) -> pd.DataFrame:
    cols = df.select_dtypes("float").columns
    return df.assign(**{c: df[c].round(casas) for c in cols})
