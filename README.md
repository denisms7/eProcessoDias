# Tramitação de Processos — tempo parado por pessoa

App Streamlit que lê a **Ficha de Tramitação de Processo** exportada do Equiplano
(relatório `500.07j rptProcessoFicha`) e mostra quanto tempo o processo ficou com cada pessoa e em cada fase.

## Executar (Windows)

Dê dois cliques em `iniciar.bat`. Na primeira vez ele cria o `.venv` e instala as dependências.

Ou, manualmente:

```bat
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\streamlit run app.py
```

## Recursos

- Upload de **um ou vários PDFs** (visão consolidada e mapa pessoa × processo).
- O PDF pode vir com todos os anexos; só as páginas da ficha são lidas (60 páginas em ~0,4 s).
- Tempo por **pessoa** e por **fase/etapa**, em dias corridos ou úteis.
- **Linha do tempo** (Gantt) e comparação de cada etapa com a **previsão** da ficha.
- Etapa atual contada até a **emissão do relatório** (auditável) ou até **agora**.
- Feriados nacionais (fixos e móveis) calculados automaticamente, mais datas municipais informadas na barra lateral.
- Download em CSV compatível com Excel pt-BR (`;` e vírgula decimal).

## Regras de cálculo

| Item | Regra |
|---|---|
| Responsável | Quem recebeu o processo (`Para`) na ocorrência |
| Permanência | Da data/hora da ocorrência até a data/hora da ocorrência seguinte |
| Última etapa | Até a data "Impresso por ... em" do PDF, ou até agora |
| Dias úteis | Art. 183 da Lei 14.133/2021: exclui o dia do início e inclui o do fim; sem sábados, domingos e feriados |
| Atraso | Tempo além do fim do dia da `Previsão` |
| Nomes | Em maiúsculas; grafias que diferem só por acento são unificadas |

## Estrutura

```
app.py                  interface Streamlit
tramitacao/parser.py    PDF -> cabeçalho + ocorrências (pypdfium2 + pypdf layout + regex)
tramitacao/analise.py   permanências, dias úteis, resumos
tramitacao/feriados.py  calendário de dias não úteis
tramitacao/graficos.py  figuras Plotly
tests/                  testes (pytest) com o PDF 2427-2026 da pasta acima
```

## Por que não Docling

O Docling usa modelos de layout e OCR (torch, alguns GB) e é pensado para documentos de estrutura
variável ou digitalizados. A ficha tem **template fixo e texto nativo**, então extração em modo layout
com regex é determinística, muito mais rápida e sem dependências pesadas. Se um dia vierem fichas
**digitalizadas** (imagem), aí sim vale plugar Docling/OCR em `extrair_texto_ficha()`.

## Testes

```bat
.venv\Scripts\python -m pytest -q
```
