"""
Tramitação de Processos — tempo parado por pessoa.

Execute:  streamlit run app.py
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime

import pandas as pd
import streamlit as st

from tramitacao import ParseError, calcular_permanencias, ler_ficha, resumo_por_fase, resumo_por_pessoa
from tramitacao.analise import arredondar
from tramitacao.feriados import dias_nao_uteis
from tramitacao import graficos as gr

st.set_page_config(page_title="Tramitação de Processos", page_icon="⏱️", layout="wide")


# ----------------------------------------------------------------------------- cache
@st.cache_data(show_spinner=False, max_entries=200)
def _ler(pdf_hash: str, _pdf: bytes, nome: str):
    p = ler_ficha(_pdf, nome)
    meta = {k: getattr(p, k) for k in ("numero", "arquivo", "data_abertura", "situacao", "requerente",
                                       "assunto", "descricao", "impresso_em", "impresso_por", "paginas_ficha")}
    return meta, p.ocorrencias


def _csv(df: pd.DataFrame) -> bytes:
    """CSV compatível com Excel pt-BR (separador ';' e vírgula decimal)."""
    return df.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig",
                     date_format="%d/%m/%Y %H:%M:%S").encode("utf-8-sig")


def _datas_extras(txt: str) -> tuple[list[date], list[str]]:
    ok, erros = [], []
    for ln in txt.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            ok.append(datetime.strptime(ln, "%d/%m/%Y").date())
        except ValueError:
            erros.append(ln)
    return ok, erros


def _num(v: float, casas: int = 1) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _duracao(dias: float) -> str:
    if dias < 1:
        h = dias * 24
        return f"{int(h)} h {int(round((h % 1) * 60))} min"
    return f"{_num(dias)} dias"


def _curto(nome: str) -> str:
    partes = nome.title().split()
    return " ".join([partes[0], partes[-1]]) if len(partes) > 2 else nome.title()


def _fmt_dh(v) -> str:
    return v.strftime("%d/%m/%Y %H:%M") if v is not None and not pd.isna(v) else "—"


# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Fichas de tramitação")
    arquivos = st.file_uploader("PDF exportado do Equiplano", type="pdf", accept_multiple_files=True,
                                help="Relatório 'Tramitação de Processo' (rptProcessoFicha). "
                                     "Pode conter os anexos — só as páginas da ficha são lidas.")
    st.divider()
    st.subheader("Contagem")
    modo_corte = st.radio("Etapa em andamento contada até",
                          ["Emissão do relatório", "Agora"], horizontal=True,
                          help="O processo ainda está com a última pessoa. A emissão do PDF é o dado "
                               "auditável; 'Agora' estima o tempo atual.")
    metrica = st.radio("Métrica dos gráficos", ["dias_corridos", "dias_uteis"],
                       format_func=gr.ROTULO_METRICA.get, horizontal=True)
    with st.expander("Dias não úteis"):
        carnaval = st.checkbox("Carnaval (ponto facultativo)", True)
        corpus = st.checkbox("Corpus Christi", True)
        extras_txt = st.text_area("Feriados municipais / pontos facultativos (dd/mm/aaaa, um por linha)",
                                  height=110, placeholder="ex.: 26/07/2026")
    st.caption("Dias úteis contados como no art. 183 da Lei 14.133/2021: exclui o dia do início "
               "e inclui o do vencimento.")

st.title("⏱️ Tramitação de processos — tempo parado por pessoa")

if not arquivos:
    st.info("Envie uma ou mais fichas de tramitação (PDF) na barra lateral.")
    st.stop()

# ----------------------------------------------------------------------------- leitura
processos, frames, falhas = [], [], []
with st.spinner("Lendo fichas..."):
    for up in arquivos:
        dados = up.getvalue()
        try:
            meta, oc = _ler(hashlib.sha256(dados).hexdigest(), dados, up.name)
        except ParseError as e:
            falhas.append(f"**{up.name}**: {e}")
            continue
        except Exception as e:  # PDF corrompido, protegido etc.
            falhas.append(f"**{up.name}**: falha ao abrir o PDF ({type(e).__name__}: {e})")
            continue
        processos.append(meta)
        frames.append(oc)

for f in falhas:
    st.error(f)
if not frames:
    st.stop()

extras, invalidas = _datas_extras(extras_txt)
if invalidas:
    st.sidebar.warning("Datas ignoradas: " + ", ".join(invalidas))

oc_all = pd.concat(frames, ignore_index=True)
duplic = pd.Series([p["numero"] for p in processos]).duplicated()
if duplic.any():
    st.warning("Processo enviado mais de uma vez; mantida a primeira ficha de cada número.")
    oc_all = oc_all.drop_duplicates(["processo", "ocorrencia"])
    processos = [p for p, d in zip(processos, duplic) if not d]

anos = range(oc_all["data"].dt.year.min(), datetime.now().year + 2)
feriados = list(dias_nao_uteis(anos, carnaval=carnaval, corpus_christi=corpus, extras=extras))

partes = []
for p in processos:
    corte = datetime.now() if modo_corte == "Agora" or p["impresso_em"] is None else p["impresso_em"]
    partes.append(calcular_permanencias(oc_all[oc_all["processo"] == p["numero"]], corte, feriados))
df = pd.concat(partes, ignore_index=True)

# ----------------------------------------------------------------------------- seleção
numeros = [p["numero"] for p in processos]
if len(numeros) > 1:
    escolha = st.selectbox("Processo", ["Todos (consolidado)"] + numeros)
else:
    escolha = numeros[0]

consolidado = escolha == "Todos (consolidado)"
dsel = df if consolidado else df[df["processo"] == escolha]
res_pessoa = resumo_por_pessoa(dsel)
res_fase = resumo_por_fase(dsel)

# ----------------------------------------------------------------------------- cabeçalho
if not consolidado:
    meta = next(p for p in processos if p["numero"] == escolha)
    st.subheader(f"Processo {meta['numero']} — {meta['assunto']}")
    st.caption(f"{meta['descricao']}  \nRequerente: {meta['requerente']} · Situação: {meta['situacao']} · "
               f"Aberto em {_fmt_dh(meta['data_abertura'])} · Relatório emitido em "
               f"{_fmt_dh(meta['impresso_em'])} por {meta['impresso_por'] or '—'} · "
               f"Páginas da ficha: {len(meta['paginas_ficha'])}")
    atual = dsel[dsel["em_andamento"]].iloc[-1]
    total_c = dsel["dias_corridos"].sum()
    total_u = int(dsel["dias_uteis"].sum())
    c = st.columns([1, 0.7, 1.5, 1, 1.1])
    c[0].metric("Tempo total", _duracao(total_c), f"{total_u} úteis", delta_color="off", delta_arrow="off")
    c[1].metric("Ocorrências", len(dsel))
    c[2].metric("Está com", _curto(atual["para"]), atual["fase_etapa"], delta_color="off", delta_arrow="off",
                help=atual["para"])
    c[3].metric("Há", _duracao(atual["dias_corridos"]), f"desde {_fmt_dh(atual['data'])}", delta_color="off", delta_arrow="off")
    atras = int((dsel["atraso_dias"] > 0).sum())
    c[4].metric("Etapas além da previsão", f"{atras} de {dsel['atraso_dias'].notna().sum()}",
                f"{_num(dsel['atraso_dias'].sum())} dias somados", delta_color="off", delta_arrow="off")
    if modo_corte == "Agora":
        st.caption("⚠️ A etapa atual está sendo contada até agora; o PDF pode estar desatualizado.")
else:
    c = st.columns(4)
    c[0].metric("Processos", len(processos))
    c[1].metric("Ocorrências", len(dsel))
    c[2].metric("Dias corridos somados", _num(dsel["dias_corridos"].sum()))
    c[3].metric("Pessoas envolvidas", dsel["para"].nunique())

# ----------------------------------------------------------------------------- abas
abas = ["Por pessoa", "Por fase/etapa", "Linha do tempo", "Prazos", "Ocorrências"]
if consolidado:
    abas.insert(1, "Pessoa × processo")
tabs = dict(zip(abas, st.tabs(abas)))

cfg_resumo = {
    "pessoa": st.column_config.TextColumn("Pessoa"),
    "fase_etapa": st.column_config.TextColumn("Fase/Etapa"),
    "passagens": st.column_config.NumberColumn("Passagens"),
    "dias_corridos": st.column_config.NumberColumn("Dias corridos", format="%.2f"),
    "dias_uteis": st.column_config.NumberColumn("Dias úteis"),
    "maior_permanencia": st.column_config.NumberColumn("Maior permanência", format="%.2f"),
    "media_permanencia": st.column_config.NumberColumn("Média por passagem", format="%.2f"),
    "atraso_total": st.column_config.NumberColumn("Dias além da previsão", format="%.2f"),
    "etapas_atrasadas": st.column_config.NumberColumn("Etapas atrasadas"),
    "percentual": st.column_config.ProgressColumn("% do tempo", format="%.1f%%", min_value=0, max_value=100),
    "com_processo_agora": st.column_config.CheckboxColumn("Com o processo"),
}

with tabs["Por pessoa"]:
    st.plotly_chart(gr.barras_resumo(res_pessoa, "pessoa", metrica, "Tempo parado por pessoa"),
                    width="stretch")
    st.dataframe(res_pessoa, hide_index=True, width="stretch", column_config=cfg_resumo)
    st.download_button("⬇️ CSV por pessoa", _csv(arredondar(res_pessoa)),
                       f"tempo_por_pessoa_{escolha.replace('/', '-')}.csv", "text/csv")

if consolidado:
    with tabs["Pessoa × processo"]:
        st.plotly_chart(gr.mapa_pessoa_processo(dsel, metrica), width="stretch")

with tabs["Por fase/etapa"]:
    st.plotly_chart(gr.barras_resumo(res_fase, "fase_etapa", metrica, "Tempo parado por fase/etapa"),
                    width="stretch")
    st.dataframe(res_fase, hide_index=True, width="stretch", column_config=cfg_resumo)
    st.download_button("⬇️ CSV por fase", _csv(arredondar(res_fase)),
                       f"tempo_por_fase_{escolha.replace('/', '-')}.csv", "text/csv")

with tabs["Linha do tempo"]:
    if consolidado:
        st.info("Selecione um processo para ver a linha do tempo.")
    else:
        st.plotly_chart(gr.linha_do_tempo(dsel), width="stretch")

with tabs["Prazos"]:
    st.caption("Previsão considerada até o fim do dia informado na ficha.")
    st.plotly_chart(gr.prazo_por_ocorrencia(dsel), width="stretch")

with tabs["Ocorrências"]:
    cols = ["processo", "ocorrencia", "data", "saida", "previsao", "de", "para", "fase_etapa",
            "confirmacao", "descricao", "dias_corridos", "dias_uteis", "atraso_dias", "em_andamento"]
    st.dataframe(
        dsel[cols], hide_index=True, width="stretch",
        column_config={
            "processo": "Processo", "ocorrencia": "Oc.", "de": "De", "para": "Para",
            "fase_etapa": "Fase/Etapa", "confirmacao": "Confirmação",
            "dias_uteis": st.column_config.NumberColumn("Dias úteis"),
            "data": st.column_config.DatetimeColumn("Entrada", format="DD/MM/YYYY HH:mm"),
            "saida": st.column_config.DatetimeColumn("Saída", format="DD/MM/YYYY HH:mm"),
            "previsao": st.column_config.DateColumn("Previsão", format="DD/MM/YYYY"),
            "dias_corridos": st.column_config.NumberColumn("Dias corridos", format="%.2f"),
            "atraso_dias": st.column_config.NumberColumn("Além da previsão", format="%.2f"),
            "descricao": st.column_config.TextColumn("Descrição", width="large"),
            "em_andamento": st.column_config.CheckboxColumn("Atual"),
        })
    st.download_button("⬇️ CSV de ocorrências", _csv(arredondar(dsel[cols])),
                       f"ocorrencias_{escolha.replace('/', '-')}.csv", "text/csv")

with st.expander("Como o tempo é calculado"):
    st.markdown(
        "- Cada ocorrência deixa o processo **com o destinatário (Para)** até a ocorrência seguinte.\n"
        "- A última etapa é contada até a emissão do relatório (ou até agora, se selecionado).\n"
        "- **Dias corridos**: diferença exata entre data/hora de entrada e saída.\n"
        "- **Dias úteis**: art. 183 da Lei 14.133/2021 — exclui o dia de início, inclui o do fim, "
        "desconta sábados, domingos, feriados nacionais e as datas locais informadas.\n"
        "- Nomes são padronizados em maiúsculas; grafias que diferem só por acento são unificadas."
    )
