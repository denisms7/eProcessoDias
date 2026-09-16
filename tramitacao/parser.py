"""
Parser da "Ficha de Tramitação de Processo" (Equiplano, relatório 500.07j rptProcessoFicha).

Estratégia:
  1. pypdfium2 (rápido) identifica as páginas que pertencem à ficha — o PDF exportado
     traz também todos os anexos (DFD, contrato, certidões...), que são ignorados.
  2. pypdf em modo "layout" extrai só essas páginas preservando o alinhamento em colunas,
     o que permite separar "De:" / "Para:" e "Fase/Etapa:" / "Confirmação:" com segurança.
  3. Regex sobre o template fixo.
"""
from __future__ import annotations

import io
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
import pypdfium2 as pdfium
from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)  # avisos de fonte dos anexos

MARCADORES_FICHA = ("Ocorrência:", "Tramitação de Processo")
FMT_DH = "%d/%m/%Y %H:%M:%S"

RE_OCORR = re.compile(
    r"Ocorr[êe]ncia:\s*(?P<num>\d+)\s+Data:\s*(?P<data>\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})"
    r"(?:\s+Previs[ãa]o:\s*(?P<prev>\d{2}/\d{2}/\d{4}))?"
)
RE_DEPARA = re.compile(r"De:\s*(?P<de>.*?)\s{2,}Para:\s*(?P<para>.+?)\s*$", re.M)
RE_FASE = re.compile(r"Fase/Etapa:\s*(?P<fase>.*?)(?:\s{2,}Confirma[çc][ãa]o:\s*(?P<conf>\S+))?\s*$", re.M)
RE_DESC = re.compile(r"^\s*Descri[çc][ãa]o:\s*(?P<txt>.*)$")
RE_IMPRESSO = re.compile(r"Impresso\s+por\s+(?P<user>.+?)\s+em\s+(?P<dh>\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})")
RE_RODAPE = re.compile(r"rptProcessoFicha\s+(?P<user>.+?),\s*(?P<dh>\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})")

RE_H_PROC = re.compile(r"Processo:\s*(?P<num>\d+/\d{4})")
RE_H_DATA = re.compile(r"Processo:.*?Data:\s*(?P<dh>\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})")
RE_H_SIT = re.compile(r"Situa[çc][ãa]o:\s*(?P<sit>.+?)\s*$", re.M)
RE_H_REQ = re.compile(r"Requerente:\s*(?P<req>.*?)(?:\s{2,}Documento:.*)?$", re.M)
RE_H_ASS = re.compile(r"Assunto:\s*(?P<ass>.+?)\s*$", re.M)

FIM_DESCRICAO = ("ANEXOS/ASSINATURAS", "rptProcessoFicha", "Autenticidade:", "Tramitação de Processo")


class ParseError(ValueError):
    """O PDF não segue o template esperado da ficha de tramitação."""


@dataclass
class Processo:
    numero: str
    arquivo: str
    data_abertura: datetime | None
    situacao: str
    requerente: str
    assunto: str
    descricao: str
    impresso_em: datetime | None
    impresso_por: str
    paginas_ficha: list[int] = field(default_factory=list)
    ocorrencias: pd.DataFrame = field(default_factory=pd.DataFrame)


def normalizar_nome(nome: str) -> str:
    """Chave canônica de pessoa: maiúsculas, espaços simples. Acentos preservados na exibição,
    mas nomes que diferem só por acento são unificados."""
    nome = re.sub(r"\s+", " ", nome or "").strip().upper()
    return nome


def _chave_sem_acento(nome: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c))


def _dh(txt: str | None, fmt: str = FMT_DH) -> datetime | None:
    if not txt:
        return None
    return datetime.strptime(re.sub(r"\s+", " ", txt.strip()), fmt)


def _paginas_ficha(pdf_bytes: bytes) -> list[int]:
    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        paginas = []
        for i in range(len(doc)):
            tp = doc[i].get_textpage()
            txt = tp.get_text_bounded()
            tp.close()
            if any(m in txt for m in MARCADORES_FICHA):
                paginas.append(i)
        return paginas
    finally:
        doc.close()


def extrair_texto_ficha(pdf_bytes: bytes) -> tuple[str, list[int]]:
    paginas = _paginas_ficha(pdf_bytes)
    if not paginas:
        raise ParseError("Nenhuma página da ficha de tramitação encontrada (marcador 'Ocorrência:').")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    texto = "\n".join(reader.pages[i].extract_text(extraction_mode="layout") for i in paginas)
    return texto, paginas


def _descricao(linhas: list[str]) -> str:
    partes: list[str] = []
    for i, ln in enumerate(linhas):
        m = RE_DESC.match(ln)
        if not m:
            continue
        partes.append(m.group("txt").strip())
        for cont in linhas[i + 1:]:
            if not cont.strip() or any(k in cont for k in FIM_DESCRICAO):
                break
            partes.append(cont.strip())
        break
    return " ".join(p for p in partes if p)


def _cabecalho(texto: str) -> dict:
    primeiro = RE_OCORR.search(texto)
    cab = texto[: primeiro.start()] if primeiro else texto[:3000]
    g = lambda rx, grp: (m.group(grp).strip() if (m := rx.search(cab)) else "")
    return {
        "numero": g(RE_H_PROC, "num"),
        "data_abertura": _dh(g(RE_H_DATA, "dh"), "%d/%m/%Y %H:%M"),
        "situacao": g(RE_H_SIT, "sit"),
        "requerente": re.sub(r"\s+", " ", g(RE_H_REQ, "req")),
        "assunto": re.sub(r"\s+", " ", g(RE_H_ASS, "ass")),
        "descricao": _descricao(cab.splitlines()),
    }


def _ocorrencias(texto: str) -> pd.DataFrame:
    marcas = list(RE_OCORR.finditer(texto))
    registros = []
    for k, m in enumerate(marcas):
        fim = marcas[k + 1].start() if k + 1 < len(marcas) else len(texto)
        bloco = texto[m.end(): fim]
        cabeca = "\n".join(bloco.splitlines()[:4])
        dp = RE_DEPARA.search(cabeca)
        fs = RE_FASE.search(cabeca)
        if not dp:
            raise ParseError(f"Ocorrência {m.group('num')}: campos De/Para não encontrados.")
        registros.append({
            "ocorrencia": int(m.group("num")),
            "data": _dh(m.group("data")),
            "previsao": _dh(m.group("prev"), "%d/%m/%Y") if m.group("prev") else None,
            "de": normalizar_nome(dp.group("de")),
            "para": normalizar_nome(dp.group("para")),
            "fase_etapa": re.sub(r"\s+", " ", fs.group("fase")).strip() if fs else "",
            "confirmacao": (fs.group("conf") or "") if fs else "",
            "descricao": _descricao(bloco.splitlines()[:40]),
        })
    if not registros:
        raise ParseError("Nenhuma ocorrência encontrada na ficha.")
    df = (pd.DataFrame(registros)
            .drop_duplicates("ocorrencia", keep="first")
            .sort_values(["data", "ocorrencia"])
            .reset_index(drop=True))
    # unifica grafias que diferem só por acento (usa a grafia mais frequente)
    todas = pd.concat([df["de"], df["para"]])
    canon = (todas.groupby(todas.map(_chave_sem_acento))
                  .agg(lambda s: s.value_counts().index[0]).to_dict())
    for col in ("de", "para"):
        df[col] = df[col].map(lambda n: canon[_chave_sem_acento(n)])
    df["previsao"] = pd.to_datetime(df["previsao"])
    return df


def _impressao(texto: str) -> tuple[datetime | None, str]:
    achados = [(m.group("dh"), m.group("user")) for m in RE_IMPRESSO.finditer(texto)]
    achados += [(m.group("dh"), m.group("user")) for m in RE_RODAPE.finditer(texto)]
    if not achados:
        return None, ""
    dh, user = min(((_dh(d), u) for d, u in achados), key=lambda x: x[0])
    return dh, normalizar_nome(user)


def ler_ficha(pdf_bytes: bytes, arquivo: str = "") -> Processo:
    texto, paginas = extrair_texto_ficha(pdf_bytes)
    cab = _cabecalho(texto)
    impresso_em, impresso_por = _impressao(texto)
    oc = _ocorrencias(texto)
    oc.insert(0, "processo", cab["numero"] or arquivo)
    return Processo(arquivo=arquivo, impresso_em=impresso_em, impresso_por=impresso_por,
                    paginas_ficha=[p + 1 for p in paginas], ocorrencias=oc, **cab)
