# Medidas DAX — Power BI (`data/powerbi/*.csv`, delimitador `;`)

Importe os 5 CSVs e crie os relacionamentos:
`fatos_financeiros[id_fonte] → fontes[id_fonte]`.

```dax
Receita Petrobras =
CALCULATE (
    SUM ( fatos_financeiros[valor] ),
    fatos_financeiros[nome_empresa] = "PETROBRAS",
    fatos_financeiros[rubrica_padronizada] = "RECEITA_LIQUIDA"
)

Margem EBITDA Petrobras =
DIVIDE (
    CALCULATE ( SUM ( fatos_financeiros[valor] ),
        fatos_financeiros[nome_empresa] = "PETROBRAS",
        fatos_financeiros[rubrica_padronizada] = "EBITDA_AJUSTADO" ),
    [Receita Petrobras]
)

Trimestre Anterior (receita Petrobras) =
CALCULATE (
    [Receita Petrobras],
    PREVIOUSQUARTER ( dCalendario[Data] )
)

Variação QoQ % =
DIVIDE ( [Receita Petrobras] - [Trimestre Anterior], [Trimestre Anterior] )

Ranking Receita =
RANKX ( ALL ( fatos_financeiros[nome_empresa] ), [Receita Empresa] )

Diferença vs Petrobras =
[Receita Empresa] - CALCULATE ( [Receita Empresa],
    fatos_financeiros[nome_empresa] = "PETROBRAS" )

Fatos com Alerta =
CALCULATE ( COUNTROWS ( fatos_financeiros ),
    TREATAS ( VALUES ( alertas_qualidade[registro_id] ), fatos_financeiros[id_fato] ) )
```

Páginas sugeridas: Executiva (KPIs), Benchmark (barras + matriz),
Evolução (linhas por trimestre), Qualidade (alertas + fila de revisão).
