# Slide deck — PetroAnalytics PoC (7 slides)

1. **Título**: Benchmark trimestral Petrobras vs 6 pares · fontes 100% públicas · painel + análise executiva.
2. **Problema**: 7 RIs, 7 formatos (PDF/XLSX/TR), 3 moedas, 2 idiomas → consolidação manual não escala.
3. **Arquitetura MVC-W**: Model (SQLite 6 tabelas) · Workers (scan/hash, parse_*, SEC CIK, qualidade) · Controllers · Views Web+GUI 25/75.
4. **ETL e qualidade**: 133 arquivos catalogados; De-Para PT/EN; USD bi via PTAX; alertas (negativo/spike/cobertura) + fila de revisão.
5. **Painel**: executiva 2T26, comparação multi-empresa, evolução 2025Q4–2026Q2, catálogo CRUD, auditoria.
6. **Benchmark 2T26** (dados do banco pós-ETL):
   - Receita: ExxonMobil 114,5 > Shell 94,7 > BP 69,1 > Chevron 67,2 > Petrobras 33,6 USD bi.
   - Lucro líquido: Exxon 14,5 > Chevron 12,2 (spike +248% QoQ, em revisão) > Shell 10,8 > Petrobras 10,4.
   - Margem EBITDA Petrobras 55,4% (18,6/33,6) — maior do grupo no trimestre.
   - Efetivo (âncora anual): Total 102,9k > BP 100,5k > Shell 96k > Exxon 61k > Petrobras 49k > Chevron 45,3k > Equinor 25k.
7. **Próximos passos**: ingestão do 3T26 sem rebuild; SEC como cross-check automático; OCR p/ PDFs escaneados; Docker.
