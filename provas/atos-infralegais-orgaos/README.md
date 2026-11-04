# Atos infralegais por órgão — ANVISA, RFB, CMN/BCB (issue #75)

Inventário **parcial** (amostra ≠ cobertura completa).

## Publicados (Markdown integral)

| ID | Órgão / edição | Fonte |
| --- | --- | --- |
| `br-federal-rdc-anvisa-2002-02-21-50` | ANVISA RDC 50/2002 — 52 tabelas pesquisáveis + fac-símile do diagrama | [BVS](https://bvsms.saude.gov.br/bvs/saudelegis/anvisa/2002/rdc0050_21_02_2002.html) |
| `br-federal-in-rfb-2022-10-17-2110` | RFB IN 2.110 — visão **vigente** SIJUT | [API SIJUT](https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/126687/visao/vigente) |
| `br-federal-in-rfb-2022-10-17-2110-original` | RFB IN 2.110 — visão **original** SIJUT | [API SIJUT](https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/126687/visao/original) |
| `br-federal-resolucao-cmn-2021-11-25-4966` | CMN Resolução 4.966 — edição **original** DOU | [DOU](https://www.in.gov.br/web/dou/-/resolucao-cmn-n-4.966-de-25-de-novembro-de-2021-362755044) |

## Variantes preservadas (não concatenadas)

| Variante | Artefato |
| --- | --- |
| RFB multivigente | `fontes/rfb-2110-multivigente.json.xz` |
| RFB DOU (conferência) | `fontes/rfb-2110-dou.html.xz` |
| Shells SPA (evidência de acesso) | `fontes/rfb-2110-shell.html.xz`, `fontes/cmn-4966-shell.html.xz` |

## Auditoria RDC 50

- Fonte HTML: 52 `<table>`; Markdown: 44 tabelas HTML + 8 pipes = **52 pesquisáveis**.
- Fac-símile do diagrama (`fac-similes/rdc-anvisa-50-2002-fig1.jpg`) **não** substitui a transcrição tabular.
- Detalhe em `reconciliacao-br-federal-rdc-anvisa-2002-02-21-50.json` → `auditoria_tabelas_diagrama`.

## Pendências residuais (sem falso negativo)

| Tema | Motivo |
| --- | --- |
| BCB exibenormativo consolidada | Shell JS; íntegra original via DOU já publicada |
| SIJUT `link.action` shell | Angular sem corpo; API `consulta-externa` recuperou original/vigente/multivigente |
| Demais atos por órgão | Inventário aberto — amostra ≠ cobertura |

## Artefatos

- Manifesto: [`metadados/atos-infralegais-orgaos.json`](../../metadados/atos-infralegais-orgaos.json)
- Contrato: [`metadados/CONTRATO-atos-infralegais-orgaos.md`](../../metadados/CONTRATO-atos-infralegais-orgaos.md)
- Verify: `python3 scripts/atos_infralegais_orgaos.py verify`
