"""Descoberta de informacao recem-anunciada (relatorios, planilhas, arquivamentos).

O ETL responde "o que eu tenho"; a descoberta responde **"o que foi anunciado e
ainda nao esta no acervo"**. Duas fontes:

  SEC  - `data.sec.gov/submissions/CIK*.json`: formularios protocoleados com
         `reportDate` (data de referencia = fim do trimestre), `items`, flag de
         XBRL numerico. E a fonte que acerta quando o 3T foi publicado.
  RI   - paginas de resultados: extrai links de documento e classifica por
         periodo pelo nome (mesmo regex do ETL, `workers/naming.py`).

Duas saidas valiosas, ambas medidas:
  1. itens novos -> entram em `tb_fonte_dados` como DESCOBERTO (aparecem na aba
     Fontes, prontos para `coleta --baixar` e `etl --novos`);
  2. **lacunas**: o frame XBRL do trimestre alvo ainda nao existe, ou seja,
     o numero foi anunciado mas nao publicado em formato estruturado.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

import config
from workers.naming import classificar_documento, periodo_do_nome

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# Formularios que carregam resultado trimestral/anual
FORMULARIOS = ("10-Q", "10-Q/A", "10-K", "10-K/A", "6-K", "6-K/A", "20-F", "20-F/A")
# Itens de 6-K que caracterizam comunicacao de resultado
ITENS_RESULTADO = ("2.02",)

# Um 6-K protocolado na SEC e' qualquer coisa (nomeacao de diretor, assembleia,
# pagamento a governo...). So entra no acervo se tiver cara de resultado.
PALAVRAS_RESULTADO = (
    "result", "earning", "financial statement", "quarter", "quarterly",
    "interim", "annual report", "demonstra", "desempenho", "resultado",
    "earnings release", "segment", "revenue", "dividend", "buyback",
)
# Descartes explicitos: assunto que nunca carrega numero de demonstrativo
ASSUNTO_RUIDO = (
    "batch filing", "voting rights", "total voting", "changes in", "report of",
    "appointment", "appointed", "resignation", "director", "corporate governance",
    "payments to gov", "paymts to gov", "shareholder", "meeting", "proxy",
    "notice of", "announcement of", "repurchase program", "regulatory",
    "form 6-k", "form 10-q", "form 20-f",
)

FIM_DE_TRIMESTRE = {"03": "Q1", "06": "Q2", "09": "Q3", "12": "Q4"}
# Quantos anexos registrar por arquivamento (evita inundar o catalogo: um 10-Q tem ~70)
MAX_ANEXOS_POR_FILING = 6

_ULTIMA_CHAMADA = 0.0


def _throttle() -> None:
    global _ULTIMA_CHAMADA
    espera = 0.3 - (time.monotonic() - _ULTIMA_CHAMADA)
    if espera > 0:
        time.sleep(espera)
    _ULTIMA_CHAMADA = time.monotonic()


def trimestre_do_report_date(report_date: str | None) -> str | None:
    """'2026-09-30' -> '2026Q3'. Data de referencia do arquivamento = fim do trimestre."""
    if not report_date or len(report_date) < 7:
        return None
    ano, mes = report_date[:4], report_date[5:7]
    tri = FIM_DE_TRIMESTRE.get(mes)
    return f"{ano}{tri}" if tri else None


def trimestre_alvo(hoje: date | None = None) -> str:
    """Trimestre que se espera estar sendo anunciado agora (com 1 trimestre de folga)."""
    hoje = hoje or date.today()
    # resultados do trimestre T sao publicados em T+1; toleramos atraso de 1 tri
    idx = (hoje.month - 1) // 3 - 1
    ano = hoje.year + idx // 4
    return f"{ano}Q{idx % 4 + 1}"


@dataclass
class Achado:
    """Um documento anunciado que ainda nao estava no catalogo."""
    empresa: str
    origem: str                 # SEC | RI
    periodo: str                # 2026Q3 (pode ser vazio)
    tipo: str                   # PDF | XLSX | HTML
    titulo: str
    url: str
    publicado_em: str = ""
    formulario: str = ""        # 6-K, 10-Q...
    xbrl_numerico: bool = False
    motivo: str = ""             # por que foi considerado relevante
    id_fonte: int | None = None
    status: str = "NOVO"
    anexos: list[dict[str, Any]] = field(default_factory=list)
    anexos_erro: str | None = None

    def para_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResultadoEmpresa:
    empresa: str
    cik: str = ""
    alvo: str = ""
    no_banco: str = ""           # maior periodo ja carregado pelo ETL
    sec: dict[str, Any] = field(default_factory=dict)
    ri: dict[str, Any] = field(default_factory=dict)
    lacunas: list[str] = field(default_factory=list)
    situacao: str = "SEM_DADOS"

    def para_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------- SEC
def discover_sec(cik: str, empresa: str, periodo_alvo: str,
                 dias: int = 120) -> tuple[list[Achado], list[str], list[dict], str | None]:
    """(achados, lacunas_xbrl, descartados, erro) a partir do indice SEC."""
    _throttle()
    headers = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
    try:
        resp = requests.get(SUBMISSIONS.format(cik=cik.zfill(10)),
                            headers=headers, timeout=25)
        if resp.status_code != 200:
            return [], [], [], f"SEC submissions HTTP {resp.status_code}"
        dados = resp.json()
    except Exception as exc:                       # noqa: BLE001
        return [], [], [], f"{type(exc).__name__}: {exc}"

    recentes = dados.get("filings", {}).get("recent", {})
    campos = ("form", "filingDate", "reportDate", "primaryDocument",
              "accessionNumber", "items", "isXBRLNumeric", "primaryDocDescription")
    colunas = {c: recentes.get(c, []) for c in campos}
    n = len(colunas.get("form", []))
    corte = (date.today() - timedelta(days=dias)).isoformat()
    achados: list[Achado] = []
    descartados: list[dict[str, str]] = []
    vistos: set[str] = set()

    for i in range(n):
        form = colunas["form"][i]
        if form not in FORMULARIOS:
            continue
        filed = colunas["filingDate"][i]
        if filed < corte:
            continue
        doc = colunas["primaryDocument"][i]
        acc = colunas["accessionNumber"][i]
        report = colunas["reportDate"][i]
        items = (colunas.get("items") or [""])[i] or ""
        titulo = (colunas.get("primaryDocDescription") or [""])[i] or doc
        xbrl = bool(colunas.get("isXBRLNumeric", [False])[i])
        per = trimestre_do_report_date(report) or ""
        # so interessa o trimestre alvo (ou o imediatamente anterior, que e
        # reapresentacao/complemento de resultado)
        if periodo_alvo and per and per not in (periodo_alvo, _anterior(periodo_alvo)):
            continue
        if not per and form in ("10-Q", "10-K"):
            per = periodo_alvo or ""
        if not per:
            continue
        relevante, motivo = classificar_relevancia(form, titulo, items, xbrl, report, filed)
        if not relevante:
            descartados.append({"formulario": form, "data": filed,
                                "titulo": titulo[:60], "motivo": motivo})
            continue
        url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
               f"{acc.replace('-', '')}/{doc}")
        chave = f"{form}|{acc}|{doc}"
        if chave in vistos:
            continue
        vistos.add(chave)
        achado = Achado(
            empresa=empresa, origem="SEC", periodo=per, tipo="HTML",
            titulo=titulo[:120], url=url, publicado_em=filed, formulario=form,
            xbrl_numerico=xbrl, motivo=motivo)
        anexos, erro_anexo = anexos_sec(cik, acc, doc)
        achado.anexos = anexos
        achado.anexos_erro = erro_anexo
        achados.append(achado)

    lacunas = _lacunas_xbrl(cik, periodo_alvo)
    achados.sort(key=lambda a: a.publicado_em, reverse=True)
    return achados, lacunas, descartados, None


IGNORAR_ANEXO = ("-index.htm", "-index-headers.htm", ".txt", ".xml", ".xsd", ".jpg",
                 ".png", ".gif", ".pdf?x")


def anexos_sec(cik: str, accession: str, documento: str,
               tamanho_min: int = 20_000) -> tuple[list[dict[str, Any]], str | None]:
    """Documentos do arquivamento além da capa (`index.json` da pasta do filing).

    O documento principal de um 6-K costuma ser só a **capa**; as demonstrações
    financeiras vêm como anexo (EX-99.1 etc.). Sem esta etapa a descoberta via a SEC
    acharia o comunicado e perderia o número.
    """
    _throttle()
    base = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession.replace('-', '')}/")
    try:
        resp = requests.get(f"{base}index.json",
                            headers={"User-Agent": config.USER_AGENT}, timeout=25)
        if resp.status_code != 200:
            return [], f"index.json HTTP {resp.status_code}"
        itens = resp.json().get("directory", {}).get("item", [])
    except Exception as exc:                       # noqa: BLE001
        return [], f"{type(exc).__name__}: {exc}"

    anexos: list[dict[str, Any]] = []
    for it in itens:
        nome = it.get("name", "")
        baixo = nome.lower()
        if not baixo.endswith((".htm", ".html", ".txt", ".pdf", ".xlsx")):
            continue
        if any(baixo.endswith(suf) for suf in IGNORAR_ANEXO) or "index" in baixo:
            continue
        if nome == documento:
            continue
        try:
            tamanho = int(it.get("size") or 0)
        except (TypeError, ValueError):
            tamanho = 0
        tem_numero = tamanho >= tamanho_min     # capa costuma ter < 20 KB
        anexos.append({"nome": nome, "url": base + nome, "tamanho": tamanho,
                       "provavel_demonstrativo": tem_numero})
    anexos.sort(key=lambda a: -a["tamanho"])
    return anexos, None


def _anterior(periodo: str) -> str:
    """Trimestre imediatamente anterior ('2026Q1' -> '2025Q4')."""
    try:
        ano, q = int(periodo[:4]), int(periodo[-1])
    except (ValueError, IndexError):
        return ""
    return f"{ano}Q{q - 1}" if q > 1 else f"{ano - 1}Q4"


def _janela_resultado(report_date: str | None, filed: str) -> bool:
    """True se o comunicado foi protocolado logo apos o fim do trimestre (<=45 dias).

    Sem isso, todo 6-K cujo `reportDate` cai em 30/09 entrava no acervo — e a SEC
    usa essa data como referência de balanço em varios administrativos, o que
    inflava a Petrobras de 3 para 36 itens.
    """
    if not report_date:
        return False
    try:
        fim = date.fromisoformat(report_date)
        protocolado = date.fromisoformat(filed)
    except ValueError:
        return False
    if fim in (date(fim.year, 3, 31), date(fim.year, 6, 30),
               date(fim.year, 9, 30), date(fim.year, 12, 31)):
        return 0 <= (protocolado - fim).days <= 45
    return False
    try:
        ano, q = int(periodo[:4]), int(periodo[-1])
    except (ValueError, IndexError):
        return ""
    return f"{ano}Q{q - 1}" if q > 1 else f"{ano - 1}Q4"


def classificar_relevancia(formulario: str, titulo: str, items: str,
                           xbrl_numerico: bool, report_date: str | None = None,
                           protocolado: str | None = None) -> tuple[bool, str]:
    """(relevante, motivo) — separa "resultado anunciado" de comunicado administrativo.

    Sem isso, a descoberta da SEC trazia 67 itens por trimestre, sendo a maioria
    "BATCH FILING", "TOTAL VOTING RIGHTS", "APPOINTED BP CHAIR": isso suja o
    catalogo de fontes e nao alimenta nenhum fato.

    A ordem importa: o filtro de assunto vem ANTES da regra do fim de trimestre,
    senao um "TOTAL VOTING RIGHTS" com data de referencia de 30/09 passaria.
    Ja a data de referencia de fim de trimestre e o sinal mais forte para emissor
    estrangeiro (6-K com `reportDate` em 30/09 e o comunicado de resultado), e vem
    antes do teste de palavra-chave porque o titulo costuma ser apenas "6-K".
    """
    titulo = (titulo or "").strip().lower()
    if formulario in ("10-Q", "10-Q/A", "10-K", "10-K/A"):
        return True, "demonstrativo financairo protocolado na SEC"
    if any(i in (items or "") for i in ITENS_RESULTADO):
        return True, "6-K com item 2.02 (resultados de operacoes)"
    if any(a in titulo for a in ASSUNTO_RUIDO):
        return False, f"assunto administrativo ('{titulo[:32]}')"
    if (report_date or "")[-5:] in ("03-31", "06-30", "09-30", "12-31") and \
                _janela_resultado(report_date, protocolado):
        return True, (f"comunicado de resultado protocolado em {protocolado} "
                      f"(data de referencia {report_date})")
    if any(p in titulo for p in PALAVRAS_RESULTADO):
        return True, f"titulo indica resultado ('{titulo[:32]}')" + (
            " + XBRL numerico" if xbrl_numerico else "")
    return False, f"titulo sem indicacao de resultado ('{titulo[:32] or formulario}')"


def _lacunas_xbrl(cik: str, periodo_alvo: str) -> list[str]:
    """Confere se o trimestre alvo ja foi publicado em XBRL (companyfacts)."""
    if not periodo_alvo:
        return []
    _throttle()
    try:
        resp = requests.get(COMPANYFACTS.format(cik=cik.zfill(10)),
                            headers={"User-Agent": config.USER_AGENT}, timeout=30)
        if resp.status_code != 200:
            return [f"companyfacts HTTP {resp.status_code}"]
        dados = resp.json()
    except Exception:                              # noqa: BLE001
        return []
    frame = "CY" + periodo_alvo[:4] + "Q" + periodo_alvo[-1]
    encontrado = False
    for nos in dados.get("facts", {}).values():
        for node in nos.values():
            for itens in node.get("units", {}).values():
                for item in itens:
                    fr = item.get("frame") or ""
                    if fr == frame or fr == frame + "I":
                        encontrado = True
                        break
    return [] if encontrado else [f"sem frame XBRL {frame} (resultado ainda nao publicado)"]


# ---------------------------------------------------------------------- RI
def conteudo_util(bruto: bytes, nome: str) -> tuple[bool, str]:
    """Checa se o que baixou é mesmo o documento (e não login/erro do portal)."""
    head = bruto[:400].lstrip().lower()
    parece_html = head.startswith((b"<!doctype", b"<html", b"<?xml"))
    if parece_html:
        texto = bruto.decode("utf-8", errors="ignore").lower()
        # `validar_conteudo` marca qualquer <html> como rejeitado (proteção contra
        # página de login), o que rejeitaria o próprio comunicado 6-K.
        if any(p in texto for p in PALAVRAS_RESULTADO):
            return True, "BAIXADO"
        return False, "HTML sem conteúdo de resultado (provável login/erro)"
    if len(bruto) < 500:
        return False, f"conteúdo muito pequeno ({len(bruto)} bytes)"
    return True, "BAIXADO"


def baixar_achados(achados: list[dict[str, Any]], destino_dir=None) -> list[dict[str, Any]]:
    """Baixa os documentos anunciados para `data/downloads` e liga o caminho na fonte.

    Sem isso a descoberta só "vê" o documento; o arquivo precisa cair no disco
    para o `etl --novos` transformá-lo em fato.
    """
    from models.repositories import FonteRepository
    from workers.ri_collector import fetch

    pasta = destino_dir or (config.DOWNLOADS_DIR)
    repo = FonteRepository()
    resultados = []
    for a in achados:
        url = a["url"]
        nome = url.rsplit("/", 1)[-1] or "documento.htm"
        # subpasta por empresa: `empresa_do_caminho` sobe o discover a partir da
        # estrutura de pastas, entao um download "flat" cairia como DESCONHECIDA
        destino = pasta / a["empresa"] / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        try:
            bruto = fetch(url).encode("utf-8", errors="ignore")
            ok, status = conteudo_util(bruto, nome)
            if ok:
                destino.write_bytes(bruto)
                if a.get("id_fonte"):
                    repo.atualizar(a["id_fonte"], caminho_local=str(destino),
                                   extensao=Path(nome).suffix.lower().lstrip("."),
                                   nome_documento=a.get("titulo", nome)[:120],
                                   status_processamento="BAIXADO")
            resultados.append({"url": url, "arquivo": str(destino) if ok else None,
                               "status": status})
        except Exception as exc:                   # noqa: BLE001
            resultados.append({"url": url, "status": f"ERRO: {type(exc).__name__}"})
    return resultados


def _ultimo_periodo_no_banco(repo) -> str:
    with repo.db.connect() as conn:
        row = conn.execute("SELECT MAX(periodo) p FROM tb_fato_financeiro").fetchone()
    return (row["p"] if row else "") or ""


def discover_ri(empresa: str, periodo_alvo: str, urls: list[str] | None = None
                ) -> tuple[list[Achado], dict[str, Any], str | None]:
    """(achados, detalhe, erro) a partir das paginas de RI da empresa."""
    from workers.ri_collector import RI_SITES, canonical_url, discover_links

    if urls is None:
        site = RI_SITES.get(empresa)
        urls = [site] if site else []
    if not urls:
        return [], {}, "sem URL de RI configurada"
    from workers.naming import periodo_do_nome  # noqa: F401 (uso explicito abaixo)

    achados: list[Achado] = []
    detalhe: dict[str, Any] = {"paginas": [], "erros": []}
    vistos: set[str] = set()
    for url in urls:
        try:
            links = discover_links(url)
        except Exception as exc:                   # noqa: BLE001
            detalhe["erros"].append(f"{url}: {type(exc).__name__}")
            continue
        alvo_hits = 0
        for item in links:
            nome = item.get("nome") or item["url"].rsplit("/", 1)[-1]
            per = (periodo_do_nome(nome) or ("", ""))
            per = per[0] if isinstance(per, tuple) else per
            if periodo_alvo and per != periodo_alvo:
                continue
            deve, motivo = classificar_documento(nome, 1)
            if not deve:
                continue                            # narrativo: nao entra no ETL
            alvo_hits += 1
            chave = canonical_url(item["url"])
            if chave in vistos:
                continue
            vistos.add(chave)
            achados.append(Achado(empresa=empresa, origem="RI", periodo=per or periodo_alvo,
                                  tipo=item.get("tipo", "HTML"), titulo=nome[:120],
                                  url=item["url"], motivo=f"link de documento: {motivo}"))
        detalhe["paginas"].append({"url": url, "links": len(links),
                                   "do_periodo": alvo_hits})
    return achados, detalhe, None


# ------------------------------------------------------------------ orquestrador
def descobrir(periodo: str | None = None, incluir_sec: bool = True,
              incluir_ri: bool = True, registrar: bool = True,
              empresas: list[str] | None = None) -> dict[str, Any]:
    """Varre SEC e RIs, compara com o catalogo e devolve o delta por empresa.

    Quando `registrar`, cada achado entra em `tb_fonte_dados` com status
    DESCOBERTO (aparece na aba Fontes e vira alvo de `coleta --baixar`).
    """
    from models.database import DatabaseManager
    from models.repositories import FonteRepository
    from workers.ri_collector import RI_SITES

    alvo = periodo or trimestre_alvo()
    repo = FonteRepository(DatabaseManager())
    nomes = empresas or list(config.COMPANIES)
    em_rede: set[str] = set()

    def _periodos_por_empresa() -> dict[str, str]:
        """Maior período já carregado no banco por empresa (o que o ETL já cobriu)."""
        if em_rede:
            return _cache_periodos
        with repo.db.connect() as conn:
            for linha in conn.execute(
                    "SELECT nome_empresa, MAX(periodo) p FROM tb_fato_financeiro "
                    "GROUP BY 1"):
                _cache_periodos[linha["nome_empresa"]] = linha["p"] or ""
        em_rede.add("ok")
        return _cache_periodos

    _cache_periodos: dict[str, str] = {}
    resultados: list[ResultadoEmpresa] = []

    for empresa in nomes:
        cik = str(config.COMPANIES.get(empresa, {}).get("cik") or "")
        res = ResultadoEmpresa(empresa=empresa, cik=cik, alvo=alvo)

        if incluir_sec and cik:
            achados, lacunas, descartados, erro = discover_sec(cik, empresa, alvo)
            res.sec = {"novos": [a.para_dict() for a in achados],
                       "total": len(achados), "descartados": descartados[:12],
                       "descartados_total": len(descartados), "erro": erro}
            res.lacunas += lacunas
            for a in achados:
                _registrar(repo, a, registrar)
                # anexos: onde costuma estar a demonstracao financeira de verdade
                for ax in a.anexos[:MAX_ANEXOS_POR_FILING]:
                    if not ax["provavel_demonstrativo"]:
                        continue
                    anexo_fonte = Achado(
                        empresa=empresa, origem="SEC", periodo=a.periodo,
                        tipo=("XLSX" if ax["nome"].lower().endswith(".xlsx")
                              else "PDF" if ax["nome"].lower().endswith(".pdf")
                              else "HTML"),
                        titulo=ax["nome"][:120], url=ax["url"],
                        publicado_em=a.publicado_em, formulario=f"{a.formulario}/anexo",
                        motivo=(f"anexo do arquivamento ({ax['tamanho'] // 1024} KB) — "
                                f"onde fica a demonstração"))
                    _registrar(repo, anexo_fonte, registrar)
                    res.sec["anexos_registrados"] = res.sec.get("anexos_registrados", []) + [
                        {**anexo_fonte.para_dict(), "tamanho": ax["tamanho"]}]
                    res.sec["anexos"] = res.sec.get("anexos", 0) + 1

        if incluir_ri:
            achados, detalhe, erro = discover_ri(empresa, alvo)
            res.ri = {"novos": [a.para_dict() for a in achados],
                      "total": len(achados), "detalhe": detalhe, "erro": erro}
            for a in achados:
                _registrar(repo, a, registrar)

        novos = len(res.sec.get("novos", [])) + len(res.ri.get("novos", []))
        res.no_banco = _periodos_por_empresa().get(empresa, "")
        if novos and res.lacunas:
            res.situacao = "ANUNCIADO_SEM_XBRL"
        elif novos:
            res.situacao = "ANUNCIADO"
        else:
            res.situacao = "NADA_ANUNCIADO"
        resultados.append(res)

    return {
        "periodo_alvo": alvo,
        "gerado_em": date.today().isoformat(),
        "empresas": [r.para_dict() for r in resultados],
        "totais": {
            "empresas_com_novos": sum(1 for r in resultados
                                       if r.situacao != "NADA_ANUNCIADO"),
            "itens_novos": sum(len(r.sec.get("novos", [])) + len(r.ri.get("novos", []))
                               for r in resultados),
            "lacunas": sum(len(r.lacunas) for r in resultados),
        },
    }


def _registrar(repo, achado: Achado, registrar: bool) -> None:
    if not registrar:
        return
    try:
        achado.id_fonte = repo.registrar(
            nome_empresa=achado.empresa, url=achado.url, tipo=achado.tipo,
            caminho=None, cik=config.COMPANIES.get(achado.empresa, {}).get("cik"),
            status="DESCOBERTO", nome_documento=achado.titulo[:120],
            origem=f"{achado.origem}:{achado.formulario or achado.periodo or 'doc'}")
    except Exception:                              # noqa: BLE001
        achado.status = "ERRO_CATALOGO"
        return
    # dedup por URL devolve o id existente: ai da para saber se ja era conhecido
    achado.status = "NOVO" if achado.id_fonte else "ERRO_CATALOGO"


def _status_conhecido(repo, empresa: str) -> int:                 # pragma: no cover
    return sum(1 for f in repo.listar()
               if f["nome_empresa"] == empresa and f["status_processamento"] != "DESCOBERTO")


def resumo_texto(dados: dict[str, Any]) -> str:
    """Leitura humana do relatorio de descoberta."""
    linhas = [f"Descoberta {dados['gerado_em']} · alvo {dados['periodo_alvo']}",
              "=" * 78,
              f"{'empresa':<14}{'situacao':<22}{'banco ate':<12}"
              f"{'SEC':>5}{'RI':>5}  lacunas"]
    for r in dados["empresas"]:
        sec, ri = r["sec"], r["ri"]
        linhas.append(f"{r['empresa']:<14}{r['situacao']:<22}{r.get('no_banco', '-'):<12}"
                      f"{len(sec.get('novos', [])):>5}{len(ri.get('novos', [])):>5}"
                      f"  {len(r['lacunas'])}")
        for a in (sec.get("novos", []) or [])[:4]:
            linhas.append(f"    SEC {a['publicado_em']}  {a['formulario']:<5} "
                          f"{a['periodo']:<8} {a['titulo'][:38]}")
            anexos = [x for x in (a.get("anexos") or []) if x.get("provavel_demonstrativo")]
            for ax in anexos[:2]:
                linhas.append(f"        anexo: {ax['nome'][:44]} "
                              f"({ax['tamanho'] // 1024} KB) ← demonstrativo")
        if sec.get("anexos"):
            linhas.append(f"    + {sec['anexos']} anexo(s) registrado(s) como fonte")
        for a in (ri.get("novos", []) or [])[:3]:
            linhas.append(f"    RI  {a['periodo']:<13} {a['titulo'][:48]}")
        for lac in r["lacunas"]:
            linhas.append(f"    ! {lac}")
        for d in (sec.get("descartados", []) or [])[:2]:
            linhas.append(f"    x descartado: {d['data']} {d['formulario']} "
                          f"{d['motivo']}")
        for msg in (ri.get("detalhe", {}) or {}).get("erros", [])[:2]:
            linhas.append(f"    ! RI inacessivel: {msg[:74]}")
        if ri.get("total") == 0 and not (ri.get("detalhe", {}) or {}).get("erros"):
            linhas.append("    - RI sem documento do trimestre (pagina dinamica ou vazia)")
    t = dados["totais"]
    linhas.append("=" * 78)
    linhas.append(f"{t['empresas_com_novos']} empresa(s) com novidade · "
                 f"{t['itens_novos']} item(ns) novo(s) · {t['lacunas']} lacuna(s)")
    if dados.get("downloads"):
        baixados = sum(1 for d in dados["downloads"] if d["status"] == "BAIXADO")
        linhas.append(f"downloads: {baixados}/{len(dados['downloads'])} baixados "
                      f"-> rode `etl --novos` para processar")
    return "\n".join(linhas)
