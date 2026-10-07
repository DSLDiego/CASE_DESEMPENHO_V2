# Apresentação executiva — roteiro e sequência de tópicos

Deck de ~12 minutos. Cada bloco traz **o que aparece na tela** e **o que falar**.
O PDF oficial é gerado de `python app_main.py pdf` (reportlab) e o painel de
gráficos fica aberto para os números.

Sequência: utilidade → quem usa → como funciona → arquitetura → tecnologia →
resultados → qualidade → projeção → operação → riscos → próximos passos.

---

## 1. Abertura — o problema (30 s)

**Tela:** título + uma frase.

> Setores de petróleo e gás publicam os mesmos indicadores em formatos
> incompatíveis: PDF com layout, planilha com três separadores, release em inglês,
> número em dólar ou em real. Comparar Petrobras com seis pares exige planilha na
> mão e gera erro de versão.

**Gancho:** "Nenhum analyst confia no número que não sabe de onde veio. O nosso
sabe: tem fonte, data, unidade e confiança."

## 2. A utilidade — o que o sistema entrega (1 min)

**Tela:** 4 cartões (Fontes · Fatos · Qualidade · Projeção).

1. **Ver um só número comparável** entre 7 empresas, em USD bi, com a fonte da
   série inteira.
2. **Saber o que ainda não foi publicado** — a aba Descoberta responde "o que foi
   anunciado e não está no acervo".
3. **Saber o que é confiável** — DQS por empresa×trimestre e fila priorizada do que
   exige análise humana.
4. **Decidir com projeção explícita** — 3 trimestres à frente, com método escolhido
   por backtesting e intervalo de 95%, nunca misturado com fato real.

## 3. Quem usa e como usa (1 min)

**Tela:** fluxo em 4 passos.

| Passo | Comando | Perfil |
|---|---|---|
| 1. Atualizar | `python app_main.py etl --novos` (opção 3) | Analista: solta o arquivo novo e roda |
| 2. Conferir novidade | `python app_main.py descoberta` | Analista: o 3T26 já saiu? |
| 3. Ler | `app_main.py web --serve` (ou GUI) | Gestor: painel, 11 abas |
| 4. Distribuir | `app_main.py email --para ...` | e-mail com HTML+PNG+CSV |

**Frase:** "O fluxo é quarterly de verdade: soltar o arquivo, rodar um comando,
revisar a fila do que precisa de olho humano."

## 4. Como funciona — a cadeia (1,5 min)

**Tela:** seta com as etapas e o que cada uma garante.

```
Container/inventário → varredura (SHA-256) → classificação do documento
   → parser (PyMuPDF/planilha/HTML) → De-Para (PT/EN) → plausibilidade
   → carga com id_fonte + confiança → auditoria → DQS → projeção → painel
```

Três garantias que sustentam o resto:
- **Idempotência**: reexecutar não duplica nem regrada fato (SHA-256 + prioridade de confiança).
- **Rastreabilidade**: todo fato tem fonte; sem fonte ele vai para a fila.
- **Projeção ≠ fato**: projeção vive em `tb_projecao`, separada da matriz.

## 5. Arquitetura (1,5 min)

**Tela:** quatro camadas.

| Camada | Pasta | Papel |
|---|---|---|
| Model | `models/` | 12 tabelas SQLite, De-Para, glossário, repositórios |
| Worker | `workers/` | scan, `parse_tab`, `parse_pdf`, `parse_html`, SEC, qualidade, projeção, descoberta, deck |
| Controller | `controllers/` | casos de uso finos; nenhuma regra de negócio no dele |
| View | `views/` | Web (Plotly + JS), GUI (PySide6/pyqtgraph), servidor REST |

Padrões aplicados: MVC-W, repositório, injeção por construtor, SRP, `type hints`.

## 6. Tecnologia — e por quê (1 min)

**Tela:** tabela Linguagem × Uso × Motivo.

| Tecnologia | Onde | Por quê |
|---|---|---|
| **Python 3.12+** | todo o back | ecossistema de dados e automate; leitura de PDF e rede prontas |
| **SQLite** | persistência | arquivo único, sem servidor, transacional — adequado a PoC e auditável |
| **PyMuPDF** | extrair PDF | o mais rápido no acervo (2,2 s vs 6–23 s das alternativas) e acha tabelas |
| **pdfplumber** | fallback de tabela | quando o MuPDF não acha tabela válida |
| **Plotly** | Web | interativo, exporta PNG sem navegador extra |
| **PySide6 + pyqtgraph** | GUI | desktop nativo, gráficos de alta performance |
| **reportlab + Kaleido** | PDF e PNG | entregáveis sem dependência de navegador |
| **pytest** | 159 testes | regressão real (23 bugs encontrados por teste) |

**Destaque honesto:** as libs Rust de PDF (PDFOxide, pdf-inspector) foram
benchmarkadas e **não** adotadas — são redundantes com o MuPDF (mesmas 35
extrações) e 2,8× mais lentas.

## 7. Resultados medidos (1,5 min)

**Tela:** números grandes.

| Métrica | Valor |
|---|---|
| Empresas / períodos com dado | 7 · 14 trimestres (2023Q1–2026Q2) |
| Fontes catalogadas | 871 (183 com arquivo local) |
| Fatos | 272 financeiros + 121 operacionais |
| Processadas / sem dado / puladas | 26 / 82 / 52 (erros: **0**) |
| Cobertura de projeções | 10 de 10 rubricas |
| DQS médio | **75,5** (67 scorecards) |
| ETL completo → incremental | 252 s → **2–5 s** |

**Leitura executiva do 2T26 (do painel):** ExxonMobil lidera receita (114,5 USD bi)
e lucro; Shell lidera EBITDA (20,7 USD bi); margem EBITDA da Petrobras 55,4%.

## 8. Qualidade e controle (1 min)

**Tela:** 5 dimensões do DQS + fila priorizada.

- Completude 30% · Plausibilidade 25% · Consistência 15% · Rastreabilidade 15% ·
  Tempestividade 15%.
- Classificação: CONFIÁVEL ≥80 · REVISAR 60–79 · NÃO CONFIÁVEL <60.
- Fila P1/P2/P3 com código de motivo — 458 itens (60 P1, 398 P3).
- Regra de ouro: **confiança baixa vai para revisão humana, nunca para o painel
  como se fosse verdade**.

## 9. Projeção (45 s)

**Tela:** gráfico real × projetado com banda de IC95 e a tabela de cobertura.

- Método escolhido por **backtesting** (menor MAE), não por suposição:
  1 dado → repete ±15% · 2–5 → média ±2σ · ≥6 → Sazonal-Naive, Holt-Winters
  amortecido ou Última-Observação, com IC95 pela dispersão dos erros.
- 147 projeções em 49 séries, confiança média 0,58.
- A aba mostra a **cobertura por rubrica** — nenhuma rubrica com fato fica sem
  projeção sem aviso.

## 10. Governança e operação (45 s)

- Descoberta: SEC (`submissions` + `companyfacts`) diz se o trimestre foi
  protocolado e se o número estruturado já existe.
- No momento: **9 documentos relevantes da Petrobras e nenhum frame `CY2026Q3`** —
  o 3T26 foi comunicado mas o número estruturado ainda não foi publicado.
- Exceções ficam visíveis: RI de Chevron/BP bloqueia automação (403) e o relatório
  diz isso em vez de fingir cobertura.

## 11. Limites e riscos assumidos (45 s)

| Limite | Como tratamos |
|---|---|
| RI dinâmico ou bloqueado | SEC como canal confiável; bloqueio declarado no relatório |
| Documento principal do 6-K é a capa | número vem do XBRL (`companyfacts`) |
| Divergência de rubrica entre RIs | De-Para aprendido + revisão humana |
| Cobertura desigual por rubrica | DQS de completude torna visível |
| Série curta | método e confiança degradam explicitamente (`MEDIA_2DP`, conf. 0,35) |

## 12. Próximos passos (30 s)

1. Ler os **anexos** do arquivamento SEC (`index.json`) e não só o documento principal.
2. Escolher o método de projeção **por rubrica** (dívida é nível, não sazonalidade).
3. **Rolling-origin**: recalcular o passado e medir o erro real das projeções.
4. Cenários com Brent/FX e intervalo que responda à covariância dos fatores.
5. RI com render de JS para fechar o canal primário bloqueado.

---

## Perguntas que o sistema responde sozinho

- "De onde veio este número?" → `id_fonte` → documento + URL + data.
- "Esse número é confiável?" → DQS da empresa×trimestre.
- "O que ainda precisa de revisão humana?" → fila P1/P2/P3 com motivo.
- "Já saiu o resultado do próximo trimestre?" → aba Descoberta + lacuna de XBRL.
- "Quanto vamos ter no próximo trimestre?" → projeção com método e IC95.
- "Por que a despesa está negativa e o CAPEX positivo?" → aba Glossário.
