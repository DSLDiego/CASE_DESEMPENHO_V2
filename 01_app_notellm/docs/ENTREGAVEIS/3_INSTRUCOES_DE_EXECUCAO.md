# 3. Instruções para execução e atualização

Guia completo: [`../INSTRUCOES_EXECUCAO.md`](../INSTRUCOES_EXECUCAO.md) ·
Documentação de arquitetura: [`../DOCUMENTACAO_ARQUITETURA.md`](../DOCUMENTACAO_ARQUITETURA.md)

## 1. Requisitos

- Python 3.12+ e `pip install -r requirements.txt`
- Pastas: `01_app_notellm` (código), `03_Conteiner` (inventário)
- Caminhos configuráveis em `config.py`: `CONTAINER_DIR`, `DB_PATH`, `DOWNLOADS_DIR`

## 2. Primeira execução (do zero)

```bat
cd C:\Users\diego\Downloads\CASE_DESEMPENHO\01_app_notellm
python app_main.py reset          :: opcional: limpa o banco
python app_main.py full           :: ETL completo + efetivo + painel
python app_main.py web --periodo 2026Q2 --serve
```

Ou pelo menu `main_vis.bat` → opção **1**.

## 3. Menu do `main_vis.bat` (12 opções)

| # | O que faz |
|---|---|
| 1 | Pipeline ETL completo + efetivo + painel Web |
| 2 | Gerar e servir o painel Web (http://localhost:8080) |
| **3** | **Refazer ETL: varre o Container e processa SÓ os arquivos novos** |
| **4** | **Descobrir o que foi anunciado (SEC/RI) e ainda falta no acervo** |
| 5 | Interface Desktop GUI (PySide6) |
| 6 | Status do banco |
| 7 | Coleta SEC EDGAR (XBRL) |
| 8 | Âncoras anuais de efetivo |
| 9 | Coleta web RI + Investidor10 |
| 10 | Exportar slide deck em PDF |
| 11 | Enviar benchmark por e-mail (HTML + PNG + CSV) |
| 12 | Sair |

## 4. Comandos do dia a dia

| Comando | O que faz | Medido |
|---|---|---|
| `python app_main.py etl --novos` | incremental: só o que é novo (e o que falhou antes) | 252 s → **2–5 s** |
| `python app_main.py etl --jobs 4` | paralelismo do parse | 169,9 s → **102,3 s** |
| `python app_main.py descoberta` | o que foi anunciado e ainda não está no acervo | 9 itens (Petrobras 2T26) |
| `python app_main.py descoberta --baixar` | baixa os achados para `data/downloads` | 7/7 anexos da Shell |
| `python app_main.py web --periodo 2026Q2 --serve` | painel (11 abas) | HTTP 200 |
| `python app_main.py gui` | desktop (8 abas) | — |
| `python app_main.py qualidade rodar` | recalcula scorecard e alertas | 67 scorecards |
| `python app_main.py qualidade historico` | **evolução do DQS no tempo** | 70,7 → 88,3 em 14 períodos |
| `python app_main.py projeção` | recalcula projeções | 147 pontos |
| `python app_main.py derivados` | margens e alavancagem | 63 margens |
| `python app_main.py auditoria fila` | fila priorizada P1/P2/P3 | 458 itens |
| `python app_main.py auditoria decidir --id 4245 --decisão aceito` | triagem | — |
| `python app_main.py auditoria reabrir --id 4245` | **desfaz** a triagem | — |
| `python app_main.py auditoria decisoes --de ... --ate ...` | trilha de decisão do período | — |
| `python app_main.py auditoria relatorio --de ... --ate ...` | **relatório de auditoria em PDF** | 7 páginas |
| `python app_main.py fontes metrica` | mede páginas/tabelas dos PDFs (M8.12) | 133 PDFs · 6,7 pág/s |
| `python app_main.py email --para d@x.com` | e-mail com HTML + PNG + CSV | — |
| `python app_main.py pdf --periodo 2026Q2` | slide deck executivo (13 páginas) | — |
| `python -m pytest tests/ -q` | suíte | **131 passam, 2 skips** |
| `python app_main.py fontes urls` | URL quebrada x bloqueio de automação | — |
| `python app_main.py fontes cache` | cache de texto de PDF (M8.11) | — |
| `python app_main.py qualidade limiar` | limiar por empresa/rubrica (M7.22) | — |
| `python app_main.py pdf --pptx` | apresentação em PowerPoint (23 slides) | `docs/APRESENTACAO_PETROBRAS.pptx` |

## 5. Atualização trimestral (ex.: chegada do 3T26)

1. Copie os PDFs/XLSXs novos para `03_Conteiner\<EMPRESA>\<PERIODO>\`.
2. `python app_main.py descoberta` — confirme que o trimestre foi anunciado e se o
   XBRL já foi publicado (o relatório diz "sem frame XBRL CY2026Q3" enquanto não for).
3. `python app_main.py etl --novos` (opção 3) — processa só o que entrou.
4. `python app_main.py qualidade rodar` e `python app_main.py projeção`.
5. Confira `python app_main.py status` e a aba **Auditoria** do painel.
6. Para automatizar: `python app_main.py trimestre --novo 2026Q3`.

> Dica: o painel tem **duas** visões que respondem perguntas diferentes — a aba
> **Descoberta** diz *o que existe lá fora*; a aba **Gestão ETL** diz *o que entrou
> aqui e por quê*.

## 6. Ambientes sem SMTP

Sem `SMTP_HOST/USER/PASS` o app **não tenta enviar**: gera `.eml` em `data/outbox/`
para revisão humana. Com as variáveis presentes, `--enviar` faz o envio real (TLS 587).