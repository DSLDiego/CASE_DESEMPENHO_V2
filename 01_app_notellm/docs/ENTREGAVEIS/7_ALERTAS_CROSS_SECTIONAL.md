# 7. Outlier cross-sectional — quem está fora da curva no trimestre (M7.24)

## Por que está regra existe

As outras 8 regras de desvio comparam a empresa com a **própria história**: a série
caiu, o nível mudou, a confiança caiu. Elas não respondem a pergunta mais óbvia de
quem olha um benchmark de oil & gas: **está empresa está fora da curva dos pares
neste trimestre?**

Essa resposta exige uma comparação **cross-sectional** — mesma rubrica e mesmo
trimestre, calculando o z-score de cada empresa contra o grupo.

## Como o cálculo é feito

- Grupo = (trimestre, rubrica), com as empresas que têm o fato carregado.
- `z = (valor − média do grupo) ÷ desvio-padrão do grupo`.
- Limiar: **|z| ≥ 1,8** — gravado em `tb_regra_alerta`, então calibrável sem tocar em
  código. Severidade MEDIUM, e a fila trata como **P1**.
- **Mínimo de 4 empresas no grupo.** Sem esse piso, com 2 ou 3 empresas qualquer
  diferença vira z alto: a regra acusaria variação normal de uma bilateral dentro
  de um grupo minúsculo.
- Só entra o que é comparável entre empresas de oil & gas: RECEITA_LIQUIDA,
  EBITDA_AJUSTADO, LUCRO_LIQUIDO, CAPEX, FCO e DIVIDA_LIQUIDA. Marcadores
  operacionais ficam de fora — efetivo menor é o esperado numa empresa com menos
  Employees, não é anomalia.

## Os 10 achados na base atual

| Empresa | Trimestre | Métrica | Posição no grupo |
|---|---|---|---|
| CHEVRON | 2024Q2 | FCO 35.23 | +1.8σ do grupo (7 empresas, média 15.91) |
| EXXONMOBIL | 2024Q2 | LUCRO_LIQUIDO 9.24 | +1.8σ do grupo (6 empresas, média 3.43) |
| EXXONMOBIL | 2025Q2 | LUCRO_LIQUIDO 7.08 | +2.0σ do grupo (7 empresas, média 3.42) |
| EXXONMOBIL | 2025Q2 | FCO 24.50 | +1.9σ do grupo (7 empresas, média 11.56) |
| BP | 2025Q4 | LUCRO_LIQUIDO -3.42 | -2.1σ do grupo (6 empresas, média 1.78) |
| CHEVRON | 2025Q4 | FCO 33.94 | +2.3σ do grupo (7 empresas, média 12.35) |
| CHEVRON | 2026Q1 | FCO 29.85 | +2.4σ do grupo (7 empresas, média 9.21) |
| PETROBRAS | 2026Q1 | CAPEX 0.01 | -1.9σ do grupo (6 empresas, média 3.61) |
| CHEVRON | 2026Q2 | FCO 45.32 | +2.0σ do grupo (7 empresas, média 20.35) |
| PETROBRAS | 2026Q2 | CAPEX 0.01 | -1.9σ do grupo (5 empresas, média 3.02) |

## O achado que importa

**CAPEX da Petrobras = 0,01 USD bi** em 1T26 e 2T26, contra pares em 3,09 a 6,19
(no 2T26: Chevron 4,54 · Shell 4,03 · TotalEnergies 3,45 · BP 3,09). O CAPEX da
Petrobras no 4T25 era 6,29 — a série não caiu 98%, o valor **não foi extraído**.

Causa rastreada: a planilha `Excel 2T26 USD.xlsx` (fonte 2067) tem uma aba
"Investimentos" em que as linhas são **projetos**, com colunas de capacidade e
cronograma. O rótulo "Investimentos" aparece, mas o número da linha não é o
investimento consolidado — o parser leu a linha e extraiu 0,01.

O número errado estava na base, somando 0,01 em vez de ~7 bi, e a comparação
com os pares foi o que o revelou. Sem a regra, passaria despercebido até alguém
olhar a série da Petrobras e notar que o CAPEX tinha desaparecido.

## Efeito no produto

- 10 itens novos na fila, todos P1; `RUBRICA_AUSENTE` continua P3.
- A regra aparece em "Regras ativas e limiares" (aba Qualidade) com o limiar lido
  do banco.
- Implementada em `workers/quality_score.py::detectar_cross_sectional`, ligada na
  fila junto com as demais e coberta por
  `test_outlier_cross_sectional_detecta_empresa_fora_da_curva`, que verifica os
  dois lados (colagem e afastamento) e o piso de 4 empresas.
