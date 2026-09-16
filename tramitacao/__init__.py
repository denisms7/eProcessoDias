"""Leitura e análise da ficha de tramitação de processos (Equiplano - rptProcessoFicha)."""
from .parser import ParseError, Processo, ler_ficha
from .analise import calcular_permanencias, resumo_por_fase, resumo_por_pessoa

__all__ = ["ParseError", "Processo", "ler_ficha",
           "calcular_permanencias", "resumo_por_pessoa", "resumo_por_fase"]
