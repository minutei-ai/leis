# Matriz por critério — issues #63 e #94 (PR empilhado sobre #107)

Gerado na retomada de textos/anexos. Issues permanecem abertas. Contagem sozinha ≠ completude.

## #63 Emendas CF/1988 1–141

| Critério | Estado | Notas / provas |
| --- | --- | --- |
| Matriz por número, data, fonte e situação da coleta | **satisfeito** | `provas/emendas-cf1988/serie-1-141/matriz-serie.json` (141/141) |
| Textos integrais + dispositivos autônomos/anexos/transitórias | **parcial** | 141 atos publicados; mapa de dispositivos com 3 lacunas de segmentação heurística (`mapa-constituicao-adct-dispositivos.json`) |
| Distinguir CF/1988 × revisão × históricas | **satisfeito** | |
| Vínculos Constituição/ADCT → ato/dispositivos | **satisfeito** | Mapa estruturado no escopo literal do issue (sem mapa CF inteira) |
| Metadados/hashes por edição (contrato) | **satisfeito** | Frontmatter `contrato_versao=1` nos 141; 79 antigos preenchidos (`manifesto-frontmatter.json`); captura original desconhecida permanece explícita |
| Não recontar consolidada | **satisfeito** | |

Resumo: satisfeitos=5 parciais=1 pendentes=0; `issue_fechavel=false`.

## #94 RCN — anexos essenciais

| Critério | Estado | Notas / provas |
| --- | --- | --- |
| Catálogo Senado reconciliado (88) | **satisfeito** | `reconciliacao-rcn.json` |
| Markdown integral com anexos | **satisfeito** (neste avanço) | 88/88 publicados após recuperação das 6 ANX |
| PDF ANX Senado HTTP 200 / 0 bytes | **bloqueio de URL** | `bloqueio-anexos-rcn-pdf-vazio.json` — não prova inacessibilidade global |
| Fontes alternativas oficiais (Câmara/Senado HTML) | **satisfeito** | `anexos-rcn/recuperacao-fontes-alternativas.json` + fac-símiles PNG + transcrições |
| Colação visual / transcrição | **satisfeito** | `anexos-rcn/facsimiles/*.png.xz` e `*.anexo.txt.xz` |

### Contagens RCN

| Catálogo Senado | Publicado | Anexos pendentes |
| ---: | ---: | ---: |
| 88 | **88** | **0** |

### Fontes alternativas usadas nos 6 ANX

| Slug | Fonte alternativa |
| --- | --- |
| RCN 2/2025 | Câmara legin anexo PDF |
| RCN 1/2025 | Câmara legin anexo PDF (DCN 8/2025) |
| RCN 2/2014 | Câmara publicação original HTML (Estatuto AP-CPLP no corpo) |
| RCN 3/2013 | Câmara legin anexo PDF |
| RCN 2/2006 | Senado HTML 36751146 (PDF 36751141 vazio) — Estatuto de Montevidéu |
| RCN 1/2006 | Câmara legin anexo PDF |

## Não feito / limites

- Merge / fechamento de issues
- README agregado (fora deste PR filho, salvo se já herdado do #107)
- #65/#66/#89 restantes (fora do escopo deste avanço #63/#94 anexos)
- Segmentação heurística de 3 emendas no mapa de dispositivos permanece explícita
- Fac-símile prevalece sobre transcrição em divergência visual

## Test plan

- [x] `python3 scripts/emendas_cf1988_serie_1_141.py verify`
- [x] `python3 scripts/rcn_anexos_fontes_alternativas.py verify`
- [x] `python3 -m unittest tests.test_emendas_cf1988_serie_1_141 tests.test_especies_legislativas_federais -v`
