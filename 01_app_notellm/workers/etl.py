"""Worker orquestrador ETL: scan -> parse -> de-para -> carga -> qualidade.

Cada arquivo processado grava status, duracao (ms), nº de extracoes e a mensagem de
erro em `tb_fonte_dados`; cada execucao do pipeline vira uma linha em `tb_etl_execucao`
(ambos alimentam o painel "Gestao ETL" do web e da GUI).
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

from config import CONFIDENCE_MIN, PERIODS
from workers.naming import deve_parsear_documento, moeda_do_nome, normalizar_nome
from models.database import DatabaseManager
from models.repositories import DeParaRepository, FatoRepository, FonteRepository, QualityRepository
from models.depara import resolve
from workers.parse_pdf import parse_pdf
from workers.parse_tab import RawExtraction, parse_tab
from workers.parse_txt import parse_txt
from workers.quality import brl_milhoes_para_usd_bi, run_audit
from workers.scanner import scan_container

OPERACIONAIS = {"EFETIVO_TOTAL", "PRODUCAO_BOED", "FUT_REFINO"}

# Limites de plausibilidade (USD bi, trimestre/posicao). Acima -> tenta re-escala.
LIMITES = {
    "RECEITA_LIQUIDA": (0.0, 300.0), "LUCRO_BRUTO": (0.0, 200.0),
    "DESPESA_OPERACIONAL": (-300.0, 50.0), "EBITDA_AJUSTADO": (-50.0, 150.0),
    "LUCRO_LIQUIDO": (-80.0, 100.0), "FCO": (-50.0, 200.0), "FCL": (-50.0, 120.0),
    "DIVIDA_BRUTA": (0.0, 900.0), "DIVIDA_LIQUIDA": (-50.0, 700.0),
    "CAPEX": (0.0, 120.0),
}


def escolher_parser(caminho: Path):
    ext = caminho.suffix.lower()
    if ext in (".xlsx", ".xlsm", ".xls", ".csv"):
        return parse_tab
    if ext == ".pdf":
        return parse_pdf
    if ext in (".txt", ".docx"):
        return parse_txt
    if ext in (".htm", ".html"):
        from workers.parse_html import parse_html
        return parse_html
    return None


def deve_parsear_pdf(caminho: Path) -> bool:
    """Decisao por REGEX sobre o nome normalizado (ver workers/naming.py).

    Antes era substring em nome cru: 'Transcricao 1T25.pdf' (com acento) nao
    casava 'transcricao' e era parseado; 'Demonstracoes ... US$' dependia da
    grafia exata. Agora acento/espaco/hifen/cifrao viram token neutro.
    """
    return deve_parsear_documento(caminho)[0]


def motivo_skip_pdf(caminho: Path) -> str:
    """Motivo legivel da exclusao, para log/diagnostico do inventario."""
    return deve_parsear_documento(caminho)[1]


def normalizar_sinal(canon: str, valor: float) -> float:
    """Padroniza sinais: CAPEX como magnitude positiva, despesa como redutora."""
    if canon == "CAPEX" and valor < 0:
        return round(abs(valor), 4)
    if canon == "DESPESA_OPERACIONAL" and valor > 0:
        return round(-valor, 4)
    return valor


def plausivel(rubrica: str, valor: float) -> tuple[float, float, bool]:
    """Aplica limites; tenta re-escala /1000 (ex.: dolares lidos como milhoes)."""
    if rubrica not in LIMITES:
        return valor, 0.0, True
    lo, hi = LIMITES[rubrica]
    conf_penalty, ok = 0.0, lo <= valor <= hi
    tentativas = 0
    while not ok and tentativas < 3 and valor > hi:
        valor /= 1000.0
        conf_penalty += 0.05
        tentativas += 1
        ok = lo <= valor <= hi
    return round(valor, 4), conf_penalty, ok


def prioridade_arquivo(caminho: Path) -> int:
    """0 = melhor fonte, 2 = pior. Moeda detectada por regex (US$, R$, 'em dolar')."""
    nome = normalizar_nome(caminho.name)
    moeda = moeda_do_nome(caminho.name)
    if moeda == "BRL":
        return 2  # BRL convertido: processa por ultimo, nunca sobrescreve USD
    if moeda == "USD" or re.search(r"\b(databook|supplement|earnings|results)\b", nome):
        return 0
    return 1


def _diagnostico_sem_dados(gravou_algo: bool, descartados: int, para_revisao: int,
                           fora_escopo: int, n_extracoes: int,
                           alvos: set[str]) -> str | None:
    """Mensagem do status SEM_DADOS: por que nada foi gravado, sem culpar o parser.

    Antes toda fonte sem carga recebia "parser nao extraiu periods de {...}", o que
    era falso em ~metade dos casos (extracao existia, mas perdia para o fato que ja
    estava no banco ou ia para a fila de revisao).
    """
    if gravou_algo:
        return None
    if n_extracoes == 0:
        return "parser nao extraiu nenhuma linha numerica deste documento"
    motivos = []
    if para_revisao:
        motivos.append(f"{para_revisao} em revisao (confianca/plausibilidade)")
    if descartados:
        motivos.append(f"{descartados} ignoradas: fato existente com confianca maior")
    if fora_escopo:
        motivos.append(f"{fora_escopo} fora dos periodos-alvo")
    if motivos:
        return f"extraiu {n_extracoes}, mas nada foi gravado: " + "; ".join(motivos)
    return f"extraiu {n_extracoes} em periodos-alvo, sem carga ({len(alvos)} periodos)"


def _parse_em_paralelo(tarefas: list[tuple[int, Path, object]],
                       jobs: int) -> dict[int, tuple[Exception | None, float, list, dict]]:
    """Parse dos arquivos em processos separados.

    Devolve {id_fonte: (erro, ms, extracoes, metrica)}.

    Só o parse vai para paralelo: ele é a parte cara (PDF e planilha) e não toca
    no banco. A carga continua sequencial no processo principal, na ordem de
    prioridade das fontes — assim a regra "fato bom nunca é rebaixado" e o
    resultado do ETL não dependem da ordem de conclusão das tarefas.
    """
    if not tarefas:
        return {}
    # serial e paralelo usam o MESMO caminho (workers.parse_task.parse_arquivo), que
    # resolve o parser pelo caminho do arquivo — assim os dois modos só podem dar
    # o mesmo resultado, por construção.
    from workers.parse_task import parse_arquivo

    if jobs <= 1 or len(tarefas) == 1:
        return {id_fonte: parse_arquivo(str(caminho))
                for id_fonte, caminho, _ in tarefas}

    from concurrent.futures import ProcessPoolExecutor
    from concurrent.futures.process import BrokenProcessPool
    from workers.parse_task import parse_arquivo

    resultado: dict[int, tuple[Exception | None, float, list, dict]] = {}
    # `parse_arquivo` nunca levanta excecao; qualquer erro vindo de fut.result()
    # e de infraestrutura (pool morto / modulo nao importavel no filho). Nesses
    # casos caimos para serial — marcar 100+ arquivos como ERRO seria mentira.
    try:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(parse_arquivo, str(caminho)): (id_fonte, caminho)
                       for id_fonte, caminho, _ in tarefas}
            for fut, (id_fonte, caminho) in futures.items():
                resultado[id_fonte] = fut.result()
    except (BrokenProcessPool, OSError, ImportError, AttributeError, TypeError):
        return _parse_em_paralelo(tarefas, 1)
    except Exception:                              # noqa: BLE001
        return _parse_em_paralelo(tarefas, 1)
    return resultado


def run_etl(db: DatabaseManager | None = None, apenas_periodos: set[str] | None = None,
            parse_pdfs: bool = True, only_new: bool = False,
            jobs: int | None = None) -> dict:
    """Carrega o Container. `only_new=True` processa somente os arquivos novos.

    O modo incremental varre o Container, coleta os ids recem-descobertos e
    restringe o parse a eles — o que evita reprocessar centenas de PDFs.
    `jobs` controla o paralelismo do parse (None = automático, pelo nº de cores).
    """
    db = db or DatabaseManager()
    fontes = FonteRepository(db)
    depara = DeParaRepository(db)
    fatos = FatoRepository(db)
    quality = QualityRepository(db)

    # Parse paralelo: 1 = serial. O automatico deixa uma CPU livre para o SQLite.
    n_cpus = os.cpu_count() or 2
    jobs = max(1, min(jobs if jobs is not None else max(1, n_cpus - 1), 8))

    # Painel de gestão do ETL: cada execução vira uma linha em tb_etl_execucao.
    id_execucao = fontes.abrir_execucao()
    resumo = {"scan": {}, "arquivos_processados": 0, "extracoes": 0, "cargas": 0,
              "revisao": 0, "pulados_pdf": 0, "erros": 0, "nao_baixados": 0,
              "descartados": 0, "paginas_lidas": 0, "tabelas_detectadas": 0,
              "pdfs_medidos": 0}
    novos_ids: set[int] = set()
    try:
        resumo["scan"] = scan_container(fontes, novos_ids=novos_ids if only_new else None)
    except Exception as exc:                      # varredura é opcional p/ o pipeline
        resumo["scan"] = {"erro": str(exc)}
        resumo["erros"] += 1
    alvos = apenas_periodos or set(PERIODS)

    if only_new:
        resumo["modo"] = "incremental"
        # Incremental = o que entrou no inventario **e** o que foi baixado mas nunca
        # processado **e** o que falhou antes (fila de retry, M6.7). Sem a segunda
        # parte, o ciclo descoberta -> download -> fato nao fecha; sem a terceira, um
        # PDF corrompido ficaria em ERRO para sempre mesmo depois de arrumado.
        candidatos = [r for r in fontes.listar()
                      if r["id_fonte"] in novos_ids
                      or (r["caminho_local"] and not r["data_processamento"])
                      or (r["status_processamento"] == "ERRO" and r["caminho_local"])]
        # Fontes ja falhadas antes continuam elegiveis: sao "novas" no sentido util.
        arquivos = sorted(candidatos, key=lambda r: (prioridade_arquivo(Path(r["caminho_local"] or "")),
                                                     r["caminho_local"] or ""))
    else:
        arquivos = sorted(fontes.listar(), key=lambda r: (prioridade_arquivo(Path(r["caminho_local"] or "")),
                                                          r["caminho_local"] or ""))
    # --- fase 1: selecao (barato, no processo principal) -------------------------------
    a_processar: list[tuple[int, Path, object]] = []
    for row in arquivos:
        caminho = Path(row["caminho_local"] or "") if row["caminho_local"] else None
        # Fonte web descoberta mas nunca baixada NAO e erro: e "NAO_BAIXADO".
        if caminho is None:
            fontes.registrar_processamento(row["id_fonte"], "NAO_BAIXADO")
            resumo["nao_baixados"] += 1
            continue
        if not caminho.is_file():
            # ja estava catalogada com caminho local e o arquivo sumiu = erro real
            fontes.registrar_processamento(row["id_fonte"], "ERRO",
                                          erro=f"arquivo local ausente: {caminho}")
            resumo["erros"] += 1
            continue
        parser = escolher_parser(caminho)
        if parser is None:
            fontes.registrar_processamento(row["id_fonte"], "SEM_PARSER")
            continue
        if caminho.suffix.lower() == ".pdf":
            deve, motivo = deve_parsear_documento(caminho)
            if not parse_pdfs:
                fontes.registrar_processamento(row["id_fonte"], "NAO_PROCESSADO",
                                              erro="parse de PDF desativado (--sem-pdf)")
                resumo["pulados_pdf"] += 1
                continue
            if not deve:
                # grava o MOTIVO: sem isso a coluna Erro fica vazia e nao da para
                # saber se o PDF foi barrado por ser transcricao ou por tamanho
                fontes.registrar_processamento(row["id_fonte"], "NAO_PROCESSADO",
                                              erro=f"PDF pulado: {motivo}", n_extracoes=0)
                resumo["pulados_pdf"] += 1
                continue
        a_processar.append((row["id_fonte"], caminho, parser))

    # --- fase 2: parse em paralelo (a parte cara: PDF e planilha) ---------------
    # O parse e CPU-bound e nao escreve no banco, entao pode ir para processos
    # separados. A carga continua NO PROCESSO PRINCIPAL e na ordem de prioridade,
    # o que preserva a regra "fato bom nunca e rebaixado" e a reprodutibilidade.
    parseados = _parse_em_paralelo(a_processar, jobs)
    resumo["jobs"] = jobs
    resumo["parse_paralelo"] = jobs > 1 and len(a_processar) > 1

    # --- fase 3: carga sequencial (regras de negocio, prioridade e status) ------
    por_id = {r["id_fonte"]: r for r in arquivos}
    for id_fonte, caminho, _parser in a_processar:
        row = por_id[id_fonte]
        erro_parse, duracao, extracoes, metrica = parseados[id_fonte]
        # M8.12: throughput de leitura do PDF (paginas/seg por documento).
        paginas = int(metrica.get("paginas_lidas") or 0)
        tabelas = int(metrica.get("tabelas") or 0)
        if metrica:
            resumo["pdfs_medidos"] += 1
            resumo["paginas_lidas"] += paginas
            resumo["tabelas_detectadas"] += tabelas
        if erro_parse is not None:
            exc = erro_parse
            fontes.registrar_processamento(id_fonte, "ERRO", duracao,
                                          erro=f"{type(exc).__name__}: {exc}"[:500])
            quality.para_revisao(row["nome_empresa"], "?", "?", None,
                                 f"falha de parsing em {caminho.name}: {exc}", 0.0)
            resumo["revisao"] += 1
            resumo["erros"] += 1
            continue
        resumo["arquivos_processados"] += 1
        gravou_algo = False
        # contadores por arquivo: transformam SEM_DADOS em diagnostico util
        descartados = 0      # extracao em conflito com fato ja existente (melhor)
        para_revisao = 0     # extracao barrada por confianca/plausibilidade
        fora_escopo = 0      # periodo fora da janela-alvo
        for ext in extracoes:
            if ext.periodo not in alvos:
                fora_escopo += 1
                continue
            resumo["extracoes"] += 1
            rotulo = ext.extras.get("rotulo_origem", ext.rubrica)
            canon, fator = depara.resolver(row["nome_empresa"], rotulo)
            if canon is None:
                canon, _, fator = resolve(rotulo)
                if canon is None:
                    canon = ext.rubrica
                depara.upsert(row["nome_empresa"], rotulo, canon, "DRE", fator)
            valor = round(ext.valor * (fator or 1.0), 4)
            conf = ext.confianca
            if ext.moeda_origem == "BRL" and canon not in OPERACIONAIS:
                valor = brl_milhoes_para_usd_bi(valor * 1000.0, ext.periodo)
                conf -= 0.05
            if canon == "CAPEX":
                valor = normalizar_sinal(canon, valor)  # outflow -> magnitude
            if canon not in OPERACIONAIS:
                valor, penalty, ok = plausivel(canon, valor)
                conf -= penalty
                if not ok:
                    quality.para_revisao(row["nome_empresa"], ext.periodo, canon, valor,
                                         f"fora do limite de plausibilidade ({caminho.name})", conf)
                    resumo["revisao"] += 1
                    para_revisao += 1
                    continue
            if canon == "DESPESA_OPERACIONAL":
                valor = normalizar_sinal(canon, valor)  # redutora (apos plausibilidade)
            if conf < CONFIDENCE_MIN:
                quality.para_revisao(row["nome_empresa"], ext.periodo, canon, valor,
                                     f"confianca {conf:.2f} em {caminho.name}", conf)
                resumo["revisao"] += 1
                para_revisao += 1
                continue
            if ext.moeda_origem == "BRL":
                existente = fatos.obter(row["nome_empresa"], ext.periodo, canon)
                if existente and existente.get("moeda") == "USD":
                    descartados += 1      # fonte USD direta prevalece
                    continue
            if canon == "PRODUCAO_BOED" and valor < 100:
                valor = round(valor * 1000.0, 3)  # Mboed -> kboed
            if canon not in OPERACIONAIS:
                existente = fatos.obter(row["nome_empresa"], ext.periodo, canon)
                if existente and (existente.get("confianca") or 0) > round(conf, 3):
                    descartados += 1      # nunca rebaixa fato bom
                    continue
            if canon in OPERACIONAIS:
                fatos.upsert_operacional(row["nome_empresa"], ext.periodo, canon,
                                         valor, ext.unidade, row["id_fonte"])
            else:
                fatos.upsert_financeiro(row["nome_empresa"], ext.periodo, canon, valor,
                                        "USD", row["id_fonte"], round(conf, 3))
            resumo["cargas"] += 1
            gravou_algo = True
        status = "PROCESSADO" if gravou_algo else "SEM_DADOS"
        erro = _diagnostico_sem_dados(gravou_algo, descartados, para_revisao,
                                      fora_escopo, len(extracoes), alvos)
        resumo["descartados"] += descartados
        fontes.registrar_processamento(id_fonte, status, duracao, erro=erro,
                                      n_extracoes=len(extracoes),
                                      n_paginas=metrica.get("paginas"),
                                      n_paginas_lidas=metrica.get("paginas_lidas"),
                                      n_tabelas=metrica.get("tabelas"))
    resumo["auditoria"] = run_audit(db)
    # Contrato de dados: tipos, nulos, dominios e convencao de sinal (M7.26).
    # Roda ao fim da carga para que numero invalido apareca aqui e nao semanas depois.
    try:
        from workers.data_contract import rodar_contrato
        resumo["contrato"] = rodar_contrato(db)
    except Exception as exc:                       # noqa: BLE001
        resumo["contrato"] = {"ok": True, "erro": f"{type(exc).__name__}: {exc}"}
    # Proveniencia (M7.27): classifica cada fato como primario/secundario/derivado.
    # Fora do try de proposito — se a classificacao falhar, os numeros continuam
    # carregados e o pipeline nao inteiro por causa de um campo de rotulo.
    try:
        from workers.provenance import anotar_fatos
        resumo["proveniencia"] = anotar_fatos(db)
    except Exception as exc:                       # noqa: BLE001
        resumo["proveniencia"] = {"erro": f"{type(exc).__name__}: {exc}"}
    fontes.fechar_execucao(id_execucao, arquivos=resumo["arquivos_processados"],
                           extracoes=resumo["extracoes"], cargas=resumo["cargas"],
                           pulados=resumo["pulados_pdf"], revisao=resumo["revisao"],
                           erros=resumo["erros"],
                           paginas=resumo["paginas_lidas"],
                           tabelas=resumo["tabelas_detectadas"],
                           detalhe=(f"modo={resumo.get('modo', 'completo')} · "
                                    f"periodos={sorted(alvos)} · "
                                    f"novos={resumo['scan'].get('novos', 0)} · "
                                    f"nao_baixados={resumo['nao_baixados']}"))
    fontes.exportar()
    return resumo
