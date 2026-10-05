# Caminho principal: buscar → download → ETL — erros, inconsistências e melhorias

Fluxo: `RI → Discovery → Qualification → Download → RAW imutável → Parse →
Canonical → Extract+evidência → Normalização → Quality/Reconciliação → Load → Painel`.

## Erros e inconsistências possíveis por etapa
1. **Buscar**: RI com JavaScript/paginação/API (link estático não acha nada); URL sem extensão;
   mesmo documento em 2 URLs (duplicidade); página fora do ar / 429 / robots.
2. **Download**: 429/5xx sem retry perde arquivo; `.part` órfão após queda; 304 mal tratado
   rebaixa metadados; ETag muda sem mudar conteúdo (reprocesso inútil); arquivo gigante
   estoura RAM (leitura dupla: salvar + hash + parse); XLSM com macro executada (risco);
   MIME ≠ extensão (html salvo como .pdf).
3. **Parse**: PDF escaneado retorna texto vazio (sem OCR vira "0 extrações" silencioso);
   XLS com merged cells desloca colunas; encoding errado (latin1 vs utf8); `.doc`
   legado sem conversor quebra o worker.
4. **Extract**: regex captura nº da coluna errada (Q2 vs 6M vs comparativo); "Adjusted" e
   "reportado" misturados; Quarter vs YTD; moeda/escala (bn vs mm, BRL vs USD) sem
   normalização; confiança baixa publicada sem revisão.
5. **Load/estado**: 2 workers gravando → `database is locked`; re-download sem checar
   SHA reprocessa tudo; manifest por URL perde histórico quando a URL muda.

## Melhorias propostas (implementadas neste subsistema)
- **Checar antes de baixar**: `scripts/check_new.py` compara links da página com o CSV
  de downloads (`known_urls`) — só baixa o novo; score<50 vai p/ revisão, não download.
- **Tudo registrado**: cada arquivo → 1 linha em `data/source_downloads.csv`
  (datetime, fonte, URL, path, SHA, status); fontes em `config/ri_registry.json`
  com `last_check_at/last_download_at` (CRUD em GUI + CLI).
- **Download resiliente**: retry/backoff, `.part`+rename atômico, streaming, ETag/304,
  limite por host (não agredir o RI), SHA-256 p/ deduplicar mesmo conteúdo em URLs distintas.
- **Falha isolada**: quarantine/DLQ — 1 arquivo ruim não para o lote; reprocesso seletivo.
- **Porta aberta p/ V4**: OCR só p/ SCANNED_PDF, extrator por empresa/documento,
  reconciliação release×DF, EWMA de custo p/ scheduler (ver `docs/etl_architecture.md`).
