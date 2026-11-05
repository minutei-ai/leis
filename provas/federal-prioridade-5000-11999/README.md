# Provas — prioridade #71 (leis 5.000–11.999)

Lote das normas essenciais da lista prioritária da issue #71, recuperadas do
Planalto com cobertura fonte→Markdown integral (inclui normalização tipográfica
de ordinais partidos, ex. Lei 9.784). A série ampla 5.000–11.999 (1966–2009)
continua em reconciliação e coleta retomável — não para em amostras.

## Arquivos

| Caminho | Papel |
| --- | --- |
| `prioridades-catalogo.json` | 94 prioridades + `ja_no_acervo` |
| `fontes.json` / `fontes/*.htm.xz` | Capturas oficiais do lote prioritário |
| `reconciliacao-*.json` | Cobertura por documento |
| `manifesto.json` | Metadados do lote |
| `PENDENCIAS-prioridade.md` | Prioridades publicadas / já cobertas / restantes |
| `senado-anual/senado-LEI-YYYY.json` | Snapshots anuais do catálogo Senado (1966–2009) |
| `catalogo-serie-reconciliacao.json` | Reconciliação por identidade da faixa 5000–11999 |
| `serie-estado/collect-state.json` | Estado retomável da coleta da série |
| `serie-estado/collect-summary.json` | Resumo da última onda de coleta |
| `ferramentas.json` | Versões |

Capturas brutas da série (`serie-estado/capturas/`) ficam fora do Git; o estado
retomável e o catálogo de reconciliação entram no repositório.

## Reprodução

```bash
python3 scripts/federal_prioridade_5000_11999.py verify
python3 scripts/federal_prioridade_5000_11999.py reconcile-serie
python3 scripts/federal_prioridade_5000_11999.py collect-serie --limit 200
python3 -m unittest tests.test_federal_prioridade_5000_11999 -v
```

Normas já publicadas por outros lotes (#62 / núcleos) não são republicadas aqui;
aparecem em `PENDENCIAS-prioridade.md` e em `ja_no_acervo`. HTTP 404 ou falha
de transporte não prova inexistência da lei.
