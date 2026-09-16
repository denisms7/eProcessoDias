"""Calendário de dias não úteis (feriados nacionais fixos, móveis e municipais)."""
from __future__ import annotations

from datetime import date, timedelta

FIXOS_NACIONAIS = {  # (mês, dia): nome
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (9, 7): "Independência",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (11, 20): "Dia Nacional de Zumbi e da Consciência Negra",  # Lei 14.759/2023
    (12, 25): "Natal",
}


def pascoa(ano: int) -> date:
    """Algoritmo de Meeus/Jones/Butcher."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def dias_nao_uteis(anos: range | list[int], *, carnaval: bool = True, corpus_christi: bool = True,
                   extras: list[date] | None = None) -> dict[date, str]:
    out: dict[date, str] = {}
    for ano in anos:
        for (m, d), nome in FIXOS_NACIONAIS.items():
            out[date(ano, m, d)] = nome
        p = pascoa(ano)
        out[p - timedelta(days=2)] = "Sexta-feira Santa"
        if carnaval:
            out[p - timedelta(days=48)] = "Carnaval (ponto facultativo)"
            out[p - timedelta(days=47)] = "Carnaval (ponto facultativo)"
        if corpus_christi:
            out[p + timedelta(days=60)] = "Corpus Christi"
    for d in extras or []:
        out.setdefault(d, "Feriado/ponto facultativo local")
    return dict(sorted(out.items()))
