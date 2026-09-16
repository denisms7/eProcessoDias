"""Figuras Plotly usadas pelo app."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

AZUL, LARANJA, VERMELHO, CINZA = "#2a6fdb", "#e08a00", "#c8412f", "#8a8f98"
ROTULO_METRICA = {"dias_corridos": "Dias corridos", "dias_uteis": "Dias úteis"}


def _fmt_dias(v: float, metrica: str) -> str:
    if metrica == "dias_uteis":
        v = int(v)
        return f"{v} útil" if v == 1 else f"{v} úteis"
    return f"{v:.1f} d"


def barras_resumo(res: pd.DataFrame, eixo: str, metrica: str, titulo: str) -> go.Figure:
    d = res.sort_values(metrica).copy()
    total = d[metrica].sum() or 1
    d["rotulo"] = [f"{_fmt_dias(v, metrica)}  ({v / total * 100:.1f}%)" for v in d[metrica]]
    d["status"] = d["com_processo_agora"].map({True: "Com o processo agora", False: "Já encaminhou"})
    fig = px.bar(
        d, x=metrica, y=eixo, orientation="h", color="status", text="rotulo",
        color_discrete_map={"Já encaminhou": AZUL, "Com o processo agora": LARANJA},
        custom_data=["dias_corridos", "dias_uteis", "passagens", "maior_permanencia", "etapas_atrasadas"],
        labels={metrica: ROTULO_METRICA[metrica], eixo: ""}, title=titulo,
    )
    fig.update_traces(
        textposition="outside", cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Dias corridos: %{customdata[0]:.2f}<br>Dias úteis: %{customdata[1]}"
                      "<br>Passagens: %{customdata[2]}<br>Maior permanência: %{customdata[3]:.2f} d"
                      "<br>Etapas além da previsão: %{customdata[4]}<extra></extra>",
    )
    fig.update_layout(
        template="plotly_white", height=max(320, 42 * len(d) + 120), legend_title_text="",
        legend=dict(orientation="h", y=-0.12), margin=dict(l=10, r=10, t=60, b=40),
        yaxis=dict(categoryorder="array", categoryarray=d[eixo].tolist()),
        xaxis=dict(range=[0, d[metrica].max() * 1.35 if len(d) else 1]),
    )
    return fig


def linha_do_tempo(df: pd.DataFrame) -> go.Figure:
    d = df.copy()
    d["rotulo"] = "Oc. " + d["ocorrencia"].astype(str)
    fig = px.timeline(
        d, x_start="data", x_end="saida", y="para", color="fase_etapa",
        hover_data={"rotulo": True, "de": True, "descricao": True, "dias_corridos": ":.2f",
                    "dias_uteis": True, "fase_etapa": False, "para": False},
        labels={"para": "", "fase_etapa": "Fase/Etapa"},
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickformat="%d/%m", hoverformat="%d/%m/%Y %H:%M")
    fig.update_layout(template="plotly_white", height=max(320, 42 * d["para"].nunique() + 160),
                      legend=dict(orientation="h", y=-0.2), margin=dict(l=10, r=10, t=30, b=40))
    return fig


def prazo_por_ocorrencia(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["atraso_dias"]).sort_values(["processo", "ocorrencia"]).copy()
    multi = d["processo"].nunique() > 1
    d["rot"] = ((d["processo"] + " ") if multi else "") + "Oc. " + d["ocorrencia"].astype(str) + " · " + d["para"]
    d["cor"] = d["atraso_dias"].gt(0).map({True: "Além da previsão", False: "Dentro da previsão"})
    fig = px.bar(d, x="rot", y="dias_corridos", color="cor",
                 color_discrete_map={"Além da previsão": VERMELHO, "Dentro da previsão": CINZA},
                 hover_data={"atraso_dias": ":.2f", "previsao": "|%d/%m/%Y", "rot": False},
                 labels={"rot": "", "dias_corridos": "Dias corridos", "cor": ""})
    fig.update_xaxes(categoryorder="array", categoryarray=d["rot"].tolist())
    fig.update_layout(template="plotly_white", height=460, xaxis_tickangle=-40,
                      legend=dict(orientation="h", y=1.08), margin=dict(l=10, r=10, t=30, b=10))
    return fig


def mapa_pessoa_processo(df: pd.DataFrame, metrica: str) -> go.Figure:
    piv = df.pivot_table(index="para", columns="processo", values=metrica, aggfunc="sum", fill_value=0)
    piv = piv.loc[piv.sum(axis=1).sort_values(ascending=False).index]
    fig = px.imshow(piv, text_auto=".1f" if metrica == "dias_corridos" else "d", aspect="auto",
                    color_continuous_scale="Blues", labels=dict(color=ROTULO_METRICA[metrica], x="", y=""))
    fig.update_layout(height=max(320, 32 * len(piv) + 120), margin=dict(l=10, r=10, t=30, b=10))
    return fig
