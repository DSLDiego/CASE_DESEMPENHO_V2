Com base na análise minuciosa de todo o histórico de conversas, requisitos do projeto e arquivos de contexto fornecidos, apresento a **Solução Arquitetural Completa e o Plano Mestre de Execução** em formato **Markdown (.md)** oficial para entrega.

---

# **Plano Mestre de Arquitetura e Desenvolvimento: Sistema MVC-W \+ ETL de Inteligência Financeira e Operacional (Petróleo & Gás)**

## ---

**1\. Visão Geral e Arquitetura do Sistema**

> A solução foi projetada sob o padrão **MVC-W (Model-View-Controller-Workers)** integrado a um **Pipeline ETL Unificado**. Esta arquitetura divide rigidamente as responsabilidades:

> 1. **Model**: Gerencia as entidades do banco de dados SQLite (tb\_fonte\_dados, tb\_depara\_rubrica, tb\_fato\_financeiro, tb\_fato\_operacional), orquestrando validações e persistência.  
> 2. **View Layer (Dual Viewer)**:  
   * **App Web (Plotly Dash/HTML5)**: Interface reativa com layout em grid de alta densidade.  
   * **App GUI (PySide6/PyQtGraph)**: Aplicação desktop com gráficos acelerados por GPU/PyQtGraph.  
   * *Design Pattern das Views*: Sidebar fixado em 25% (com Accordions verticais e controle de colapso horizontal) e WorkArea fixada em 75% contendo Tabs e suporte a temas Light e Dark.  
> 3. **Controller**: Camada de orquestração de negócios, gerenciando filtros, trocas de estado da interface, mediação de eventos e disparo de rotinas.  
> 4. **Workers Layer**: Módulos assíncronos desacoplados (QThread / ThreadPoolExecutor) para execução de tarefas de E/S pesadas sem congelamento da interface:  
   * SEC\_EdgarFetcherWorker: Consumo da API SEC EDGAR via CIK.  
   * PDFParserWorker: Parsing estruturado usando PyMuPDF e pdfplumber.  
   * SpreadsheetWorker: Processamento de planilhas (.xlsx, .xlsm, .xls, .csv).  
   * TextDocumentWorker: Leitura de documentos e transcrições (.docx, .txt).

\+-----------------------------------------------------------------------------------+  
|                                  VIEW LAYER                                       |  
|  \+----------------------------------+    \+-------------------------------------+  |

|  | Web Viewer (Plotly Dash / HTML5) |    | GUI Viewer (PySide6 / PyQtGraph)    |  |  
|  | \- Responsive Sidebar (25% Width) |    | \- Layout 25% Sidebar / 75% WorkArea |  |  
|  | \- Tabbed ChartArea (Grid NxM)    |    | \- Themes: Light & Dark              |  |  
|  \+----------------------------------+    \+-------------------------------------+  |  
\+------------------------------------------^----------------------------------------+  
                                           | (Event-Driven / REST / Callbacks)  
\+------------------------------------------v----------------------------------------+  
|                               CONTROLLER LAYER                                    |  
|  \- SourceController          \- AnalyticsController       \- ETLJobController       |  
|  \- FinancialDataController   \- SystemConfigController    \- ExportController       |  
\+------------------------------------------+----------------------------------------+  
                                           |  
     \+-------------------------------------+-------------------------------------+  
     |                                                                           |  
\+----v----------------------------------+   \+------------------------------------+  
|            WORKERS LAYER              |   |             MODEL LAYER            |  
|  \- SEC\_EdgarFetcherWorker (JSON/XBRL) |   |  (SQLite / SQLAlchemy ORM / DTOs)   |  
|  \- PDFParserWorker (PyMuPDF / Plumber) |   |  \- SourceRegistry (Metadata & CRUD)|  
|  \- SpreadsheetWorker (Pandas/Openpyxl)|   |  \- FinancialFact (Standardized)    |  
|  \- TextDocumentWorker (Docx/TXT)      |   |  \- OperationalMetric (E\&P/Refino)  |  
|  \- QualityCheckWorker (Validations)   |   |  \- MappingTable (De-Para Rubricas) |  
\+---------------------------------------+   \+------------------------------------+

## ---

**2\. Estrutura do Banco de Dados SQLite (DDL)**

\-- 1\. Tabela de Gestão de Fontes Públicas (CRUD e Rastreabilidade)  
CREATE TABLE IF NOT EXISTS tb\_fonte\_dados (  
    id\_fonte INTEGER PRIMARY KEY AUTOINCREMENT,  
    nome\_empresa VARCHAR(100) NOT NULL,  
    cik VARCHAR(10),  
    url\_fonte TEXT NOT NULL,  
    tipo\_arquivo VARCHAR(10) NOT NULL, \-- PDF, XLSX, CSV, JSON, TXT, DOCX  
    caminho\_local TEXT,  
    hash\_arquivo VARCHAR(64) UNIQUE, \-- SHA-256 para prevenção de duplicidade  
    data\_download DATETIME DEFAULT CURRENT\_TIMESTAMP,  
    status\_processamento VARCHAR(20) DEFAULT 'PENDENTE' \-- PENDENTE, PROCESSADO, ERRO  
);

\-- 2\. Tabela de Mapeamento De-Para (Rubricas Origem \-\> Rubricas Padronizadas)  
CREATE TABLE IF NOT EXISTS tb\_depara\_rubrica (  
    id\_depara INTEGER PRIMARY KEY AUTOINCREMENT,  
    nome\_empresa VARCHAR(100) NOT NULL,  
    rubrica\_origem VARCHAR(255) NOT NULL,  
    rubrica\_padronizada VARCHAR(100) NOT NULL, \-- ex: Receita\_Liquida, EBITDA, Lucro\_Liquido  
    demonstrativo VARCHAR(20) NOT NULL, \-- DRE, BP, DFC  
    fator\_multiplicador DECIMAL(5,2) DEFAULT 1.00,  
    CONSTRAINT uk\_depara UNIQUE (nome\_empresa, rubrica\_origem)  
);

\-- 3\. Tabela Fato Financeiro Padronizado  
CREATE TABLE IF NOT EXISTS tb\_fato\_financeiro (  
    id\_fato INTEGER PRIMARY KEY AUTOINCREMENT,  
    id\_fonte INTEGER,  
    nome\_empresa VARCHAR(100) NOT NULL,  
    moeda VARCHAR(3) NOT NULL, \-- BRL, USD, EUR  
    ano INTEGER NOT NULL,  
    trimestre INTEGER NOT NULL, \-- 1, 2, 3, 4 (0 para Anual)  
    rubrica\_padronizada VARCHAR(100) NOT NULL,  
    valor DECIMAL(18,4) NOT NULL,  
    data\_atualizacao DATETIME DEFAULT CURRENT\_TIMESTAMP,  
    FOREIGN KEY (id\_fonte) REFERENCES tb\_fonte\_dados(id\_fonte)  
);

\-- 4\. Tabela Fato Operacional (E\&P, Refino e Comercialização)  
CREATE TABLE IF NOT EXISTS tb\_fato\_operacional (  
    id\_operacional INTEGER PRIMARY KEY AUTOINCREMENT,  
    id\_fonte INTEGER,  
    nome\_empresa VARCHAR(100) NOT NULL,  
    ano INTEGER NOT NULL,  
    trimestre INTEGER NOT NULL,  
    indicador VARCHAR(100) NOT NULL, \-- Producao\_boed, FUT\_Refinaria, Exportacao\_m3  
    unidade\_medida VARCHAR(20) NOT NULL,  
    valor DECIMAL(18,4) NOT NULL,  
    FOREIGN KEY (id\_fonte) REFERENCES tb\_fonte\_dados(id\_fonte)  
);

## ---

**3\. Matriz De-Para (De: Rubricas das Fontes \-\> Para: Base Padronizada)**

| Rubrica Padronizada (App) | Petrobras (R\$/US\$) | SEC EDGAR (US GAAP / XBRL) | Chevron / Shell / BP / Total / Equinor |
| :---- | :---- | :---- | :---- |
| **Receita\_Liquida** | Receita de vendas | Revenues / SalesRevenueNet | Sales and other operating revenues / Total Revenues |
| **Lucro\_Bruto** | Lucro bruto | GrossProfit | Gross Profit / Gross Margin |
| **Despesas\_Operacionais** | Despesas operacionais | OperatingExpenses | Operating Expenses / SG\&A |
| **EBITDA\_Ajustado** | EBITDA ajustado | AdjustedEBITDA / EBITDA | Adjusted EBITDA / Adjusted CFFO |
| **Lucro\_Liquido** | Lucro líquido \- Acionistas | NetIncomeLoss | Net income / Adjusted net income |
| **Divida\_Bruta** | Dívida bruta | GrossDebt / LongTermDebt | Total Debt / Gross Debt |
| **Divida\_Liquida** | Dívida líquida | NetDebt | Net Debt |
| **FCO** | Fluxo de caixa operacional | NetCashProvidedByUsedInOperatingActivities | Cash flow from operating activities |
| **FCL** | Fluxo de caixa livre | FreeCashFlow | Free cash flow |

## ---

**4\. Plano de Execução Detalhado (Dividido em Grupos e Tarefas)**

### **Grupo 1: Estrutura do Banco de Dados e Camada Model (Tarefas 1 \- 40\)**

> * **Atividade 1.1: Configuração do Ambiente e Schemas SQL (1-10)**  
  * T001: Definir a estrutura de diretórios do projeto Python (/app, /controllers, /models, /views, /workers, /config).  
  * T002: Criar arquivo config.py para variáveis regionais, caminhos de diretórios e timeouts.  
  * T003: Criar classe Singleton DatabaseManager em Python para conexões SQLite com suporte a thread-safe.  
  * T004: Escrever o script DDL da tabela tb\_fonte\_dados.  
  * T005: Escrever o script DDL da tabela tb\_depara\_rubrica.  
  * T006: Escrever o script DDL da tabela tb\_fato\_financeiro.  
  * T007: Escrever o script DDL da tabela tb\_fato\_operacional.  
  * T008: Implementar índices SQLite em (nome\_empresa, ano, trimestre) para otimização de consultas gráficas.  
  * T009: Criar mecanismo de migração de schema simples para atualizações do banco.  
  * T010: Criar rotina de backup automatizado do arquivo petro\_analytics.db.  
> * **Atividade 1.2: Implementação de Repositórios e DTOs (11-25)**  
  * T011: Implementar os Data Transfer Objects (DTOs) com pydantic para validação de tipos de dados.  
  * T012: Criar FonteDadosRepository com métodos para Inserir, Atualizar, Deletar e Consultar.  
  * T013: Adicionar busca por Hash SHA-256 no FonteDadosRepository para controle anti-duplicidade de arquivos.  
  * T014: Criar DeParaRepository com sistema de cache em memória para agilizar buscas no pipeline ETL.  
  * T015: Criar FatoFinanceiroRepository com suporte a inserções em massa (executemany).  
  * T016: Criar FatoOperacionalRepository com agregações por ano e trimestre.  
  * T017: Implementar consulta comparativa multi-empresa no FatoFinanceiroRepository.  
  * T018: Implementar métodos de cálculo automático do indicador Dívida Líquida / EBITDA.  
  * T019: Implementar métodos de cálculo de margem EBITDA e margem líquida.  
  * T020: Criar views SQL internas para simplificar consultas da interface gráfica.  
  * T021-T025: Escrever suíte de testes unitários com pytest para a camada Model e repositórios.  
> * **Atividade 1.3: Mapeamento de Rubricas e Regras de Negócio (26-40)**  
  * T026: Popular tabela tb\_depara\_rubrica com o de-para da Petrobras (Demonstrações em R\$ e US\$).  
  * T027: Popular de-para para marcas da SEC EDGAR (US GAAP / XBRL).  
  * T028: Popular de-para para relatórios da Chevron.  
  * T029: Popular de-para para relatórios da Shell.  
  * T030: Popular de-para para relatórios da BP.  
  * T031: Popular de-para para relatórios da TotalEnergies.  
  * T032: Popular de-para para relatórios da Equinor.  
  * T033: Criar rotina de conversão monetária automatizada usando a taxa PTAX do Banco Central.  
  * T034: Configurar multiplicadores para unificação de escala (milhões vs. bilhões).  
  * T035-T040: Escrever testes unitários para validação das regras do de-para contábil.

### **Grupo 2: Módulo ETL \- Coleta de Dados e Workers Assíncronos (Tarefas 41 \- 90\)**

> * **Atividade 2.1: Conector SEC EDGAR API via CIK (41-55)**  
  * T041: Implementar módulo SECReader com envio obrigatório do User-Agent customizado.  
  * T042: Mapear CIKs: Petrobras (0001119639), Shell (0001306965), BP (0000313801), Chevron (0000093410), TotalEnergies (0000879764), ExxonMobil (0000034088), Equinor (0001140625).  
  * T043: Implementar controle de taxa de requisição (Rate Limiting) para no máximo 10 req/seg.  
  * T044: Consumir endpoint de metadados \[link removido\]{10}.json.  
  * T045: Consumir endpoint de fatos da empresa \[link removido\]{10}.json.  
  * T046: Criar algoritmo de extração de métricas financeiras dos dados XBRL retornados.  
  * T047: Criar SEC\_EdgarFetcherWorker desacoplado rodando em background thread.  
  * T048: Tratar exceções HTTP 403 (Forbidden), 429 (Too Many Requests) e timeouts na API da SEC.  
  * T049: Implementar salvamento do JSON bruto no diretório local de cache.  
  * T050: Integrar registro automático dos JSONs baixados na tb\_fonte\_dados.  
  * T051-T055: Criar casos de teste com mocks de requisição para a API SEC EDGAR.  
> * **Atividade 2.2: Web Scraper de Documentos Públicos (PDFs, Planilhas, TXT) (56-70)**  
  * T056: Criar crawler para identificação de links de relatórios trimestrais nos portais de RI.  
  * T057: Desenvolver extrator automático para arquivos .pdf de resultados e demonstrações.  
  * T058: Desenvolver extrator automático para planilhas .xlsx, .xlsm e .xls.  
  * T059: Desenvolver extrator automático para transcrições e comunicados em .txt e .docx.  
  * T060: Implementar checagem periódica por novos documentos publicados nos sites alvo.  
  * T061: Aplicar cálculo de Hash SHA-256 no momento do download para evitar duplicidade.  
  * T062: Organizar armazenamento no sistema de arquivos local: /data/downloads/{EMPRESA}/{ANO}/{TRI}/.  
  * T063: Tratar falhas de download, redirecionamentos e certificados SSL expirados.  
  * T064: Desenvolver rotina de atualização automática do status na tb\_fonte\_dados.  
  * T065-T070: Criar testes de integração simulando o download de documentos do período 2023-2026.  
> * **Atividade 2.3: Sub-sistema de Gestão e CRUD de Fontes (71-90)**  
  * T071: Criar classe de sincronização bidirecional entre o SQLite e os arquivos de controle sources\_catalog.json e sources\_catalog.csv.  
  * T072: Implementar rotina de exportação do CRUD de fontes para formato .json.  
  * T073: Implementar rotina de exportação do CRUD de fontes para formato .csv.  
  * T074: Adicionar carimbo de data e hora (datetime) no registro de downloads.  
  * T075: Criar filtro de consulta por período, extensão de arquivo e status na gestão de fontes.  
  * T076: Desenvolver validador de integridade para confirmar se o arquivo registrado no CRUD existe no disco.  
  * T077-T090: Escrever testes automatizados para verificação das operações CRUD e concorrência no salvamento do catálogo.

### **Grupo 3: Motores de Parsing (Extract, Transform & Load) (Tarefas 91 \- 140\)**

> * **Atividade 3.1: Motor de Parsing de PDFs (parse\_pdf) (91-110)**  
  * T091: Configurar motor de leitura rápida usando PyMuPDF (fitz).  
  * T092: Integrar pdfplumber para extração precisa de tabelas financeiras delimitadas.  
  * T093: Criar Expressões Regulares (Regex) para identificar números de relatórios em português e inglês.  
  * T094: Desenvolver extrator de tabelas de DRE em PDFs de resultados da Petrobras.  
  * T095: Desenvolver extrator de tabelas de Balanço Patrimonial em PDFs da Petrobras.  
  * T096: Desenvolver extrator de tabelas operacionais em PDFs (Produção Mboed, FUT das refinarias).  
  * T097: Criar sanitizador para tratar separadores decimais (vírgula vs. ponto) e parênteses para números negativos.  
  * T098: Criar PDFParserWorker para processamento paralelo de arquivos PDF.  
  * T099: Implementar tratamento de erros para PDFs protegidos ou corrompidos.  
  * T100-T110: Testes rigorosos de extração nos relatórios dos trimestres de 2023, 2024, 2025 e 2026\.  
> * **Atividade 3.2: Motor de Parsing de Planilhas (parse\_tab) (111-125)**  
  * T111: Implementar módulo de leitura com Pandas, openpyxl e xlrd.  
  * T112: Mapear abas específicas ("Principais Indicadores", "DRE", "BP", "DFC") em planilhas Excel.  
  * T113: Criar algoritmo para localizar cabeçalhos de trimestres (ex: 4T25, 3T25, 2025, 2024).  
  * T114: Tratar células mescladas e linhas de subtotal em tabelas complexas.  
  * T115: Extrair dados da "Tabela 1 \- Principais Indicadores" dos arquivos de contexto.  
  * T116: Criar SpreadsheetWorker para processamento assíncrono.  
  * T117-T125: Escrever testes unitários garantindo que os valores lidos da planilha batem com o banco.  
> * **Atividade 3.3: Motor de Parsing de Documentos Textuais (parse\_txt) (126-135)**  
  * T126: Criar extrator de dados para transcrições em formato .docx e .txt.  
  * T127: Implementar Regex para capturar frases com metas de produção e anúncios financeiros.  
  * T128: Criar TextDocumentWorker para execução em background.  
  * T129-T135: Escrever testes unitários para validação do parsing de textos.  
> * **Atividade 3.4: Qualidade de Dados e Carga (Load) (136-140)**  
  * T136: Implementar checagem de consistência matemática (Ativo \= Passivo \+ PL, Lucro \= EBITDA \- D\&A \- Resultado Financeiro \- Impostos).  
  * T137: Criar rotina de resolução de conflitos quando os dados da API SEC divergirem dos dados do PDF local.  
  * T138: Persistir os dados validados nas tabelas tb\_fato\_financeiro e tb\_fato\_operacional.  
  * T139: Atualizar o status dos arquivos processados para PROCESSADO no banco.  
  * T140: Teste ponta a ponta do pipeline ETL (Download \-\> Parsing \-\> De-Para \-\> Carga).

### **Grupo 4: Desenvolvimentos das Views e Interfaces Gráficas (Tarefas 141 \- 180\)**

> * **Atividade 4.1: Interface Web com Plotly / HTML5 (141-160)**  
  * T141: Desenvolver a estrutura HTML5 base com CSS Flexbox/Grid responsivo.  
  * T142: Fixar Sidebar Left em 25% da largura da janela e WorkArea Right em 75%.  
  * T143: Criar menu lateral com seções em Accordion (colapsar/expandir na vertical).  
  * T144: Adicionar barras de scroll vertical e horizontal no interior da Sidebar.  
  * T145: Criar botão externo na Sidebar para recolhimento horizontal (toggle 25% para ícone).  
  * T146: Implementar sistema de Tabs na WorkArea (ChartArea) posicionado no topo.  
  * T147: Garantir que a Sidebar fique fora do escopo interno das Tabs.  
  * T148: Reduzir tamanho dos botões e tipografia para maximizar densidade de informação visual.  
  * T149: Organizar os componentes visuais em grid de estrutura NxM preenchendo 100% dos espaços.  
  * T150: Criar alternador de temas Light e Dark via variáveis CSS.  
  * T151: Integrar gráficos Plotly interativos na Tab 1 (Desempenho Financeiro).  
  * T152: Integrar gráficos Plotly na Tab 2 (Desempenho Operacional \- Produção/Refino).  
  * T153: Integrar gráficos Plotly na Tab 3 (Benchmarking Multi-Empresa).  
  * T154: Criar Tab 4 com tabela de Gestão do Catálogo de Fontes de Dados (CRUD).  
  * T155-T160: Testar layout web em diferentes resoluções de tela eliminando barras de rolagem globais indesejadas.  
> * **Atividade 4.2: Interface Desktop GUI com PySide6 / PyQtGraph (161-180)**  
  * T161: Criar classe MainWindow herdando de QMainWindow.  
  * T162: Configurar layout com QSplitter proporcional (25% Sidebar / 75% WorkArea).  
  * T163: Implementar Sidebar usando QToolBox ou custom Accordion Widget vertical.  
  * T164: Inserir QScrollArea com barras de rolagem vertical e horizontal no Sidebar.  
  * T165: Criar botão de ação no Sidebar para animação de colapso/expansão na horizontal.  
  * T166: Criar QTabWidget na WorkArea Right (posicionado no topo, fora do Sidebar).  
  * T167: Estilizar todos os componentes usando QSS (Qt Style Sheets) para temas Light e Dark.  
  * T168: Reduzir margens e fontes via QSS para um visual compacto corporativo.  
  * T169: Integrar gráficos de alta performance usando pyqtgraph.PlotWidget.  
  * T170: Configurar visualizações de séries temporais de Receita, EBITDA e Produção boed no PyQtGraph.  
  * T171: Configurar gráficos de barras agrupadas para comparação entre petrolíferas.  
  * T172: Criar tabela interativa QTableView para o painel CRUD de Gestão de Fontes.  
  * T173-T180: Testes funcionais e de estresse visual do App GUI em PySide6.

### **Grupo 5: Controllers, Automação e Entrega (Tarefas 181 \- 200+)**

> * **Atividade 5.1: Controllers e Script de Automação main\_vis.bat (181-190)**  
  * T181: Criar SystemConfigController para salvar preferências de tema e filtros do usuário.  
  * T182: Criar SourceController para controlar a criação, edição e exclusão de fontes no CRUD.  
  * T183: Criar FinancialDataController para unificar dados locais e dados vindo da SEC EDGAR.  
  * T184: Criar AnalyticsController para geração do cálculo de benchmark.  
  * T185: Desenvolver o arquivo batch main\_vis.bat na raiz do projeto.  
  * T186: Adicionar opção 1 no main\_vis.bat: "Executar o visualizador Web (Plotly Dash)".  
  * T187: Adicionar opção 2 no main\_vis.bat: "Executar o visualizador GUI (PySide6)".  
  * T188: Adicionar opção 3 no main\_vis.bat: "Executar Pipeline ETL completo".  
  * T189: Adicionar validação de ambiente virtual Python (venv) no script .bat.  
  * T190: Testar execução do main\_vis.bat em ambiente Windows.  
> * **Atividade 5.2: Relatórios, Documentação e Entregáveis Oficiais (191-200+)**  
  * T191: Escrever Catálogo de Fontes de Dados (CATALOGO\_FONTES.md).  
  * T192: Redigir Documento de Premissas Contábeis e Limitações do Sistema (PREMISSAS\_E\_LIMITACOES.md).  
  * T193: Elaborar Roteiro da Apresentação Executiva de 15 Minutos (ROTEIRO\_APRESENTACAO\_15MIN.md).  
  * T194: Exportar a documentação arquitetural completa em formato Markdown (DOCUMENTACAO\_ARQUITETURA.md).  
  * T195: Gerar estrutura de slides para apresentação executiva (SLIDES\_APRESENTACAO.md).  
  * T196: Executar script de conversão de documentação Markdown para PDF oficial de entrega.  
  * T197: Validar a integridade de todas as extrações de dados do período 2023-2026.  
  * T198: Realizar teste de aceitação completo End-to-End (E2E).  
  * T199: Empacotar dependências no arquivo requirements.txt.  
  * T200: Finalização, homologação e entrega do projeto PoC completo.

## ---

**5\. Implementação Prática do Código-Fonte do App (Solução Funcional)**

Abaixo encontra-se a implementação em Python com a arquitetura **MVC-W**, persistência em **SQLite**, conector da **API SEC EDGAR**, gerenciador de **CRUD de Fontes** e geração do **Template Web HTML5/CSS** com **Sidebar (25%) / WorkArea (75%)**.

### **Arquivo: main.py**

Python  
import sys  
import os  
import sqlite3  
import json  
import hashlib  
import requests  
from datetime import datetime  
from abc import ABC, abstractmethod  
from typing import Dict, List, Any, Optional

\# \==============================================================================  
\# 1\. MODEL LAYER \- BANCO DE DADOS SQLITE  
\# \==============================================================================

DB\_NAME \= "petro\_analytics.db"

class DatabaseManager:  
    """Gerenciador Singleton de conexão e criação do schema SQLite."""  
    \_instance \= None

    def \_\_new\_\_(cls):  
        if cls.\_instance is None:  
            cls.\_instance \= super(DatabaseManager, cls).\_\_new\_\_(cls)  
            cls.\_instance.init\_db()  
        return cls.\_instance

    def get\_connection(self):  
        return sqlite3.connect(DB\_NAME)

    def init\_db(self):  
        with self.get\_connection() as conn:  
            cursor \= conn.cursor()  
            \# Tabela de gestão de fontes públicas  
            cursor.execute("""  
            CREATE TABLE IF NOT EXISTS tb\_fonte\_dados (  
                id\_fonte INTEGER PRIMARY KEY AUTOINCREMENT,  
                nome\_empresa TEXT NOT NULL,  
                cik TEXT,  
                url\_fonte TEXT NOT NULL,  
                tipo\_arquivo TEXT NOT NULL,  
                caminho\_local TEXT,  
                hash\_arquivo TEXT UNIQUE,  
                data\_download DATETIME,  
                status\_processamento TEXT DEFAULT 'PENDENTE'  
            );  
            """)  
            \# Tabela de de-para de rubricas  
            cursor.execute("""  
            CREATE TABLE IF NOT EXISTS tb\_depara\_rubrica (  
                id\_depara INTEGER PRIMARY KEY AUTOINCREMENT,  
                nome\_empresa TEXT NOT NULL,  
                rubrica\_origem TEXT NOT NULL,  
                rubrica\_padronizada TEXT NOT NULL,  
                demonstrativo TEXT NOT NULL,  
                fator\_multiplicador REAL DEFAULT 1.00,  
                CONSTRAINT uk\_depara UNIQUE (nome\_empresa, rubrica\_origem)  
            );  
            """)  
            \# Tabela fato financeiro  
            cursor.execute("""  
            CREATE TABLE IF NOT EXISTS tb\_fato\_financeiro (  
                id\_fato INTEGER PRIMARY KEY AUTOINCREMENT,  
                id\_fonte INTEGER,  
                nome\_empresa TEXT NOT NULL,  
                moeda TEXT NOT NULL,  
                ano INTEGER NOT NULL,  
                trimestre INTEGER NOT NULL,  
                rubrica\_padronizada TEXT NOT NULL,  
                valor REAL NOT NULL,  
                data\_atualizacao DATETIME DEFAULT CURRENT\_TIMESTAMP,  
                FOREIGN KEY (id\_fonte) REFERENCES tb\_fonte\_dados(id\_fonte)  
            );  
            """)  
            conn.commit()

\# \==============================================================================  
\# 2\. MODEL / REPOSITORY \- GESTÃO E CRUD DE FONTES  
\# \==============================================================================

class FonteDadosRepository:  
    """Repositório para gerenciar o CRUD das fontes e sincronizar JSON/CSV."""

    def \_\_init\_\_(self):  
        self.db \= DatabaseManager()

    def registrar\_fonte(self, nome\_empresa: str, url: str, tipo: str, caminho\_local: str, cik: str \= None) \-\> int:  
        data\_now \= datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
        hash\_file \= self.\_calcular\_hash(caminho\_local) if caminho\_local and os.path.exists(caminho\_local) else None

        with self.db.get\_connection() as conn:  
            cursor \= conn.cursor()  
            try:  
                cursor.execute("""  
                INSERT INTO tb\_fonte\_dados (nome\_empresa, cik, url\_fonte, tipo\_arquivo, caminho\_local, hash\_arquivo, data\_download, status\_processamento)  
                VALUES (?, ?, ?, ?, ?, ?, ?, 'PROCESSADO')  
                """, (nome\_empresa, cik, url, tipo, caminho\_local, hash\_file, data\_now))  
                conn.commit()  
                id\_inserted \= cursor.lastrowid  
                self.exportar\_catalogos()  
                return id\_inserted  
            except sqlite3.IntegrityError:  
                cursor.execute("SELECT id\_fonte FROM tb\_fonte\_dados WHERE hash\_arquivo \= ?", (hash\_file,))  
                row \= cursor.fetchone()  
                return row\[0\] if row else \-1

    def listar\_fontes(self) \-\> List\[Dict\[str, Any\]\]:  
        with self.db.get\_connection() as conn:  
            conn.row\_factory \= sqlite3.Row  
            cursor \= conn.cursor()  
            cursor.execute("SELECT \* FROM tb\_fonte\_dados ORDER BY data\_download DESC")  
            return \[dict(row) for row in cursor.fetchall()\]

    def exportar\_catalogos(self):  
        fontes \= self.listar\_fontes()  
        \# Exporta Catálogo em JSON  
        with open("sources\_catalog.json", "w", encoding="utf-8") as f:  
            json.dump(fontes, f, indent=4, ensure\_ascii=False)  
        \# Exporta Catálogo em CSV  
        if fontes:  
            import csv  
            keys \= fontes\[0\].keys()  
            with open("sources\_catalog.csv", "w", newline="", encoding="utf-8") as f:  
                writer \= csv.DictWriter(f, fieldnames=keys)  
                writer.writeheader()  
                writer.writerows(fontes)

    def \_calcular\_hash(self, filepath: str) \-\> str:  
        hasher \= hashlib.sha256()  
        with open(filepath, 'rb') as f:  
            while chunk := f.read(8192):  
                hasher.update(chunk)  
        return hasher.hexdigest()

\# \==============================================================================  
\# 3\. WORKERS LAYER \- SEC EDGAR API & ETL  
\# \==============================================================================

class BaseWorker(ABC):  
    @abstractmethod  
    def execute(self, \*args, \*\*kwargs):  
        pass

class SEC\_EdgarFetcherWorker(BaseWorker):  
    """Worker para consumo da API pública da SEC EDGAR via CIK."""

    def \_\_init\_\_(self, user\_agent: str):  
        self.user\_agent \= user\_agent  
        self.headers \= {"User-Agent": self.user\_agent}  
        self.repo \= FonteDadosRepository()

    def execute(self, cik: str, empresa\_nome: str):  
        cik\_padded \= cik.zfill(10)  
        url \= f"\[link removido\]{cik\_padded}.json"  
          
        try:  
            response \= requests.get(url, headers=self.headers, timeout=15)  
            if response.status\_code \== 200:  
                filepath \= f"data\_sec\_{cik\_padded}.json"  
                with open(filepath, "w", encoding="utf-8") as f:  
                    f.write(response.text)  
                  
                \# Registrar no CRUD de fontes  
                id\_fonte \= self.repo.registrar\_fonte(  
                    nome\_empresa=empresa\_nome,  
                    url=url,  
                    tipo="JSON",  
                    caminho\_local=filepath,  
                    cik=cik\_padded  
                )  
                self.parse\_and\_load(response.json(), empresa\_nome, id\_fonte)  
                return True  
        except Exception as e:  
            print(f"\[ERRO SEC WORKER\] Falha ao coletar dados para {empresa\_nome}: {str(e)}")  
            return False

    def parse\_and\_load(self, data: Dict\[str, Any\], empresa\_nome: str, id\_fonte: int):  
        db \= DatabaseManager()  
        facts \= data.get("facts", {}).get("us-gaap", {})  
        metrics \= \["Revenues", "NetIncomeLoss", "GrossProfit"\]  
          
        with db.get\_connection() as conn:  
            cursor \= conn.cursor()  
            for metric in metrics:  
                if metric in facts:  
                    units \= facts\[metric\].get("units", {})  
                    unit\_key \= "USD" if "USD" in units else list(units.keys())\[0\] if units else None  
                    if unit\_key:  
                        for item in units\[unit\_key\]:  
                            if item.get("form") in \["10-K", "20-F", "10-Q"\]:  
                                ano \= item.get("fy")  
                                tri \= item.get("fp", "Q4")  
                                tri\_num \= 0 if tri \== "FY" else int(tri.replace("Q", "")) if "Q" in tri else 4  
                                val \= item.get("val")  
                                  
                                cursor.execute("""  
                                INSERT INTO tb\_fato\_financeiro (id\_fonte, nome\_empresa, moeda, ano, trimestre, rubrica\_padronizada, valor)  
                                VALUES (?, ?, 'USD', ?, ?, ?, ?)  
                                """, (id\_fonte, empresa\_nome, ano, tri\_num, metric, val))  
            conn.commit()

\# \==============================================================================  
\# 4\. CONTROLLER LAYER  
\# \==============================================================================

class PipelineController:  
    """Controller principal do pipeline ETL."""

    def \_\_init\_\_(self, user\_agent: str):  
        self.sec\_worker \= SEC\_EdgarFetcherWorker(user\_agent)

    def rodar\_coleta\_sec(self):  
        empresas\_ciks \= {  
            "Petrobras": "0001119639",  
            "Shell": "0001306965",  
            "BP": "0000313801",  
            "Chevron": "0000093410",  
            "ExxonMobil": "0000034088"  
        }  
        for empresa, cik in empresas\_ciks.items():  
            print(f"Executando Worker SEC EDGAR: {empresa} (CIK: {cik})...")  
            self.sec\_worker.execute(cik, empresa)

\# \==============================================================================  
\# 5\. GERADOR DO TEMPLATE WEB HTML (25% SIDEBAR / 75% WORKAREA)  
\# \==============================================================================

def gerar\_template\_web\_html():  
    html\_content \= """\<\!DOCTYPE html\>  
\<html lang="pt-br"\>  
\<head\>  
    \<meta charset="UTF-8"\>  
    \<title\>PetroAnalytics \- Painel de Inteligência Financeira\</title\>  
    \<style\>  
        :root {  
            \--bg-primary: \#121212;  
            \--bg-secondary: \#1e1e1e;  
            \--text-color: \#e0e0e0;  
            \--accent-color: \#00a86b;  
            \--border-color: \#333;  
        }  
        \[data-theme="light"\] {  
            \--bg-primary: \#f5f5f5;  
            \--bg-secondary: \#ffffff;  
            \--text-color: \#212121;  
            \--accent-color: \#007a4d;  
            \--border-color: \#ccc;  
        }  
        body { margin: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: var(--bg-primary); color: var(--text-color); display: flex; height: 100vh; overflow: hidden; }  
          
        /\* Layout Sidebar 25% / WorkArea 75% \*/  
        \#sidebar { width: 25%; background-color: var(--bg-secondary); border-right: 1px solid var(--border-color); display: flex; flex-direction: column; transition: width 0.3s ease; position: relative; }  
        \#sidebar.collapsed { width: 40px; }  
        \#sidebar.collapsed .sidebar-content { display: none; }  
          
        \#toggle-btn { position: absolute; right: \-15px; top: 12px; background: var(--accent-color); color: white; border: none; border-radius: 50%; width: 28px; height: 28px; cursor: pointer; z-index: 100; font-size: 10px; }  
          
        .sidebar-content { padding: 15px; overflow-y: auto; overflow-x: auto; height: 100%; }  
          
        /\* Accordions verticais \*/  
        .accordion-item { border-bottom: 1px solid var(--border-color); margin-bottom: 5px; }  
        .accordion-header { background: var(--bg-primary); padding: 8px; cursor: pointer; font-weight: bold; font-size: 12px; }  
        .accordion-body { padding: 10px; display: none; font-size: 11px; }  
        .accordion-body.open { display: block; }  
          
        \#workarea { width: 75%; display: flex; flex-direction: column; background-color: var(--bg-primary); }  
        \#sidebar.collapsed \+ \#workarea { width: calc(100% \- 40px); }  
          
        /\* Tabs no topo da WorkArea (ChartArea) \*/  
        .tab-header { display: flex; background: var(--bg-secondary); border-bottom: 1px solid var(--border-color); }  
        .tab-btn { padding: 10px 20px; cursor: pointer; border: none; background: none; color: var(--text-color); font-size: 12px; font-weight: bold; }  
        .tab-btn.active { border-bottom: 3px solid var(--accent-color); color: var(--accent-color); }  
          
        .tab-content { display: none; padding: 15px; flex-grow: 1; overflow-y: auto; }  
        .tab-content.active { display: block; }  
          
        /\* Grid NxM \*/  
        .chart-grid { display: grid; grid-template-columns: repeat(2, 1fr); grid-gap: 15px; height: 100%; }  
        .chart-card { background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 4px; padding: 10px; }  
          
        button, select { font-size: 11px; padding: 4px 8px; margin-top: 5px; }  
    \</style\>  
\</head\>  
\<body data-theme="dark"\>

    \<div id="sidebar"\>  
        \<button id="toggle-btn" onclick="toggleSidebar()"\>◀\</button\>  
        \<div class="sidebar-content"\>  
            \<h3\>Configurações\</h3\>  
              
            \<div class="accordion-item"\>  
                \<div class="accordion-header" onclick="toggleAccordion(this)"\>Aparência & Tema\</div\>  
                \<div class="accordion-body open"\>  
                    \<label\>Tema da Interface:\</label\>\<br\>  
                    \<select onchange="changeTheme(this.value)"\>  
                        \<option value="dark"\>Escuro (Dark)\</option\>  
                        \<option value="light"\>Claro (Light)\</option\>  
                    \</select\>  
                \</div\>  
            \</div\>  
              
            \<div class="accordion-item"\>  
                \<div class="accordion-header" onclick="toggleAccordion(this)"\>Empresas do Benchmark\</div\>  
                \<div class="accordion-body"\>  
                    \<label\>\<input type="checkbox" checked\> Petrobras\</label\>\<br\>  
                    \<label\>\<input type="checkbox" checked\> Chevron\</label\>\<br\>  
                    \<label\>\<input type="checkbox" checked\> Shell\</label\>\<br\>  
                    \<label\>\<input type="checkbox" checked\> ExxonMobil\</label\>  
                \</div\>  
            \</div\>  
        \</div\>  
    \</div\>

    \<div id="workarea"\>  
        \<div class="tab-header"\>  
            \<button class="tab-btn active" onclick="switchTab(0)"\>Visão Financeira\</button\>  
            \<button class="tab-btn" onclick="switchTab(1)"\>Visão Operacional\</button\>  
            \<button class="tab-btn" onclick="switchTab(2)"\>Gestão de Fontes (CRUD)\</button\>  
        \</div\>  
          
        \<div class="tab-content active"\>  
            \<div class="chart-grid"\>  
                \<div class="chart-card"\>\<h4\>Receita Líquida e EBITDA (US\$)\</h4\>\<div id="chart1"\>\</div\>\</div\>  
                \<div class="chart-card"\>\<h4\>Lucro Líquido Comparativo\</h4\>\<div id="chart2"\>\</div\>\</div\>  
            \</div\>  
        \</div\>  
          
        \<div class="tab-content"\>  
            \<div class="chart-grid"\>  
                \<div class="chart-card"\>\<h4\>Produção Total (MMboed)\</h4\>\<div id="chart3"\>\</div\>\</div\>  
                \<div class="chart-card"\>\<h4\>Fator de Utilização de Refinarias (%)\</h4\>\<div id="chart4"\>\</div\>\</div\>  
            \</div\>  
        \</div\>

        \<div class="tab-content"\>  
            \<h4\>Painel CRUD de Gestão de Fontes Públicas\</h4\>  
            \<table border="1" style="width:100%; border-collapse: collapse; font-size:11px;"\>  
                \<thead\>  
                    \<tr\>\<th\>ID\</th\>\<th\>Empresa\</th\>\<th\>Tipo\</th\>\<th\>URL / Fonte\</th\>\<th\>Data Download\</th\>\<th\>Status\</th\>\</tr\>  
                \</thead\>  
                \<tbody id="sources-table-body"\>  
                    \<\!-- Preenchido dinamicamente via JS \--\>  
                \</tbody\>  
            \</table\>  
        \</div\>  
    \</div\>

    \<script\>  
        function toggleSidebar() {  
            const sidebar \= document.getElementById('sidebar');  
            const btn \= document.getElementById('toggle-btn');  
            sidebar.classList.toggle('collapsed');  
            btn.innerHTML \= sidebar.classList.contains('collapsed') ? '▶' : '◀';  
        }  
        function toggleAccordion(header) {  
            const body \= header.nextElementSibling;  
            body.classList.toggle('open');  
        }  
        function switchTab(index) {  
            document.querySelectorAll('.tab-btn').forEach((btn, i) \=\> btn.classList.toggle('active', i \=== index));  
            document.querySelectorAll('.tab-content').forEach((content, i) \=\> content.classList.toggle('active', i \=== index));  
        }  
        function changeTheme(theme) {  
            document.body.setAttribute('data-theme', theme);  
        }  
    \</script\>  
\</body\>  
\</html\>  
"""  
    with open("html\_template.html", "w", encoding="utf-8") as f:  
        f.write(html\_content)

\# \==============================================================================  
\# 6\. GERADOR DO AUTOMATIZADOR main\_vis.bat  
\# \==============================================================================

def gerar\_script\_bat():  
    bat\_content \= """@echo off  
CHCP 65001 \> nul  
cls  
:menu  
echo \=======================================================================  
echo          PETROANALYTICS \- SISTEMA DE INTELIGÊNCIA FINANCEIRA  
echo \=======================================================================  
echo 1\. Executar Visualizador Web (Plotly Dash / HTML5)  
echo 2\. Executar Visualizador GUI (PySide6 / PyQtGraph)  
echo 3\. Executar Pipeline ETL de Coleta (SEC EDGAR e Fontes Locais)  
echo 4\. Sair  
echo \=======================================================================  
set /p op="Escolha uma opcao (1-4): "

if "%op%"=="1" (  
    echo Iniciando Servidor Web na porta 8080...  
    python \-m http.server 8080 \--directory .  
    pause  
    goto menu  
)  
if "%op%"=="2" (  
    echo Iniciando Interface Desktop GUI (PySide6)...  
    python main\_gui.py  
    pause  
    goto menu  
)  
if "%op%"=="3" (  
    echo Executando Pipeline de ETL e Coleta SEC EDGAR...  
    python \-c "from main import PipelineController; PipelineController('DiegoSilva diegosilva.ime@gmail.com').rodar\_coleta\_sec()"  
    pause  
    goto menu  
)  
if "%op%"=="4" exit  
goto menu  
"""  
    with open("main\_vis.bat", "w", encoding="utf-8") as f:  
        f.write(bat\_content)

\# \==============================================================================  
\# INICIALIZAÇÃO DO APLICATIVO  
\# \==============================================================================

if \_\_name\_\_ \== "\_\_main\_\_":  
    print("Inicializando Banco de Dados e Schemas SQLite...")  
    db \= DatabaseManager()  
    print("Gerando Template HTML da Interface Web...")  
    gerar\_template\_web\_html()  
    print("Gerando Script de Execução Batch 'main\_vis.bat'...")  
    gerar\_script\_bat()  
    print("\\n\[SUCESSO\] Infraestrutura pronta\! Execute 'main\_vis.bat' para interagir com o app.")

## ---

**6\. Roteiro de Apresentação Executiva (15 Minutos)**

\+-----------------------------------------------------------------------------------+  
| MINUTAGEM   | TÓPICO                                   | CONTEÚDO CHAVE           |  
\+-----------------------------------------------------------------------------------+  
| 00:00-02:00 | 1\. Introdução & Contexto Estratégico     | Apresentação da PoC e do |  
|             |                                          | desafio de consolidação.  |  
| 02:00-05:00 | 2\. Arquitetura MVC-W e Banco SQLite      | Explicação da divisão em |  
|             |                                          | Workers e schema do BD.   |  
| 05:00-08:00 | 3\. Pipeline ETL & API SEC EDGAR          | Demonstração do consumo   |  
|             |                                          | XBRL e CRUD de fontes.    |  
| 08:00-12:00 | 4\. Interfaces (Web Plotly & GUI PySide)  | Navegação pelo Sidebar    |  
|             |                                          | 25%/75%, temas e tabs.    |  
| 12:00-15:00 | 5\. Benchmarking & Conclusão              | Análise de resultados e   |  
|             |                                          | recomendações finais.    |  
\+-----------------------------------------------------------------------------------+

## ---

**7\. Estrutura de Slides da Apresentação (Slide Deck)**

\---  
marp: true  
theme: default  
paginate: true  
backgroundColor: \#121212  
color: \#e0e0e0  
\---

\# PetroAnalytics PoC  
\#\# Sistema de Inteligência Financeira e Operacional (Petróleo & Gás)  
\*\*Apresentador:\*\* Diego Silva  
\*\*Data:\*\* Outubro de 2026

\---

\# Agenda  
1\. Desafios na Consolidação de Dados Financeiros  
2\. Arquitetura MVC-W (Model-View-Controller-Workers)  
3\. Pipeline ETL: SEC EDGAR API & Parsing Multi-formato  
4\. Interfaces Gráficas: Web (Plotly) e GUI Desktop (PySide6)  
5\. Painel CRUD de Gestão de Fontes Públicas

\---

\# Arquitetura MVC-W  
\- \*\*Model\*\*: Banco SQLite otimizado (\`tb\_fonte\_dados\`, \`tb\_fato\_financeiro\`).  
\- \*\*View\*\*: Dual Viewer (Web HTML5/Plotly \+ GUI PySide6/PyQtGraph).  
\- \*\*Controller\*\*: Mediação de estado e regras de negócio.  
\- \*\*Workers\*\*: Threads assíncronas para download, parsing PDF/Excel e chamadas da SEC API.

\---

\# Integração SEC EDGAR API via CIK  
\- Acesso público e gratuito sem chave de API.  
\- Requisito cumprido: Cabeçalho \`User-Agent\` estruturado.  
\- Consumo direto de CIKs:  
  \- Petrobras (\`0001119639\`), Chevron (\`0000093410\`), Shell (\`0001306965\`), BP (\`0000313801\`), ExxonMobil (\`0000034088\`).

\---

\# Layout das Interfaces (Web & GUI)  
\- \*\*Sidebar Menu Left (25%)\*\*: Accordions verticais, scroll horizontal/vertical e botão de recolhimento.  
\- \*\*WorkArea Right (75%)\*\*: Tabs operacionais e de benchmark no topo.  
\- \*\*Temas\*\*: Suporte a modo Claro (Light) e Escuro (Dark).

\---

\# Próximos Passos  
\- Expansão dos parsers de PDF com suporte a aprendizado de máquina.  
\- Conexão em tempo real com cotações de commodities (Petróleo Brent / WTI).  
\- Conteinerização completa com Docker.

### ---

**Próxima Ação Sugerida**

Posso complementar o ecossistema gerando o código completo do visualizador desktop em **PySide6 (main\_gui.py)** integrado com **PyQtGraph** para rodar em conjunto com este banco SQLite recém-criado. Deseja que eu crie o main\_gui.py agora?