# Matriz por critério — PR #107 (issues #63 #65 #66 #89 #94)

Gerado na retomada do PR. Issues permanecem abertas. Contagem sozinha ≠ completude.

## #63 Emendas CF/1988 1–141

| Critério | Estado | Notas |
| --- | --- | --- |
| Criar matriz por número, data, fonte e situação da coleta, reconciliando a série com catálogo oficial | **satisfeito** | publicados=141 lacunas=0 |
| Recuperar atos integrais ausentes, incluindo dispositivos autônomos, anexos, regras transitórias | **parcial** | Heurística lexical; mapa estruturado incompleto |
| Distinguir claramente emendas da CF/1988, emendas de revisão e emendas de constituições históricas | **satisfeito** | |
| Registrar vínculos da Constituição/ADCT com o ato modificador e seus dispositivos autônomos | **parcial** | Citação textual; mapa dispositivo-a-dispositivo ainda não estruturado |
| Preservar metadados de edição/fonte/captura, hashes e provas de conversão, sem presumir vigência | **parcial** | 79 arquivos antigos ainda sem frontmatter YAML |
| Não recontar Constituição consolidada ou edições alternativas como se fossem emendas coletadas | **satisfeito** | |

Resumo: satisfeitos=3 parciais=3 pendentes=0; `issue_fechavel=False`.

## #65 DLG / #66 RSF / #89 RCD / #94 RCN

| Critério transversal | Estado atual |
| --- | --- |
| Catálogo Senado reconciliado com identidade/ID/URL/estado | satisfeito (4 espécies) |
| Coleta integral com retomada e limites de acesso | em progresso (coleta retomável; lote ampliado além de 5 amostras) |
| Rejeição de HTML erro/login e falsa íntegra | satisfeito (pipeline + testes) |
| Anexos essenciais bloqueiam publicação | satisfeito (`anexos-pendentes`; evidência PDF vazio) |
| Descoberta Câmara RCD pós-1991 | parcial (63 citações; **13** íntegras legin publicacaooriginal) |
| Completar Markdown do catálogo | pendente (milhares restantes em DLG/RSF/RCD Senado) |

### Contagens reconciliadas (Senado) + manifesto do lote

| Espécie | Catálogo Senado | Publicado (Senado) | Anexos pendentes | Identificado não coletado | Manifesto (incl. Câmara) |
| --- | ---: | ---: | ---: | ---: | ---: |
| DLG | 15944 | 335 | 0 | 15609 | 335 |
| RSF | 6578 | 335 | 0 | 6243 | 335 |
| RCD | 1885 (até 1991-09-25) | 335 | 0 | 1550 | **348** (=335 Senado + 13 Câmara) |
| RCN | 88 | 82 | **6** | 0 | 82 |

Manifesto total do lote: **1100** Markdown. Origens: normas.leg.br 350; Senado publicação HTML 737; Câmara legin publicacaooriginal 13.

### #94 RCN — bloqueio concreto de anexos

Seis RCN com corpo HTML OK e ANX `temTexto=S` cujo endpoint Senado devolve HTTP 200 `application/pdf` com **0 bytes**. Evidência: `bloqueio-anexos-rcn-pdf-vazio.json`. Não publicados (sem falsa íntegra).

### #89 RCD pós-1991

- Descoberta: 63 citações nº/ano no Regimento CD 30ª ed. (BD Câmara).
- URLs legin resolvidas: 13 em `urls-legin-camara-rcd-resolvidas.json`.
- Coletadas e publicadas: 13 (inclui RCD 16/2025).
- Restantes 50 citações: URL individual ainda não resolvida (índices `/legin/fed/rescad/YYYY/` → 403; LexML WAF; PRC ≠ promulgada).
- Comando: `collect-camara-rcd`.

## Não feito neste passo

- Merge / fechamento de issues
- README agregado / contagens globais
- Íntegra das 50 citações RCD restantes
- Recuperação dos PDF ANX RCN (fonte oficial vazia nesta captura)
- #63: frontmatter nos 79 antigos; mapa ADCT dispositivo-a-dispositivo
