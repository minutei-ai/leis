# Matriz por critério — PR #107 (issues #63 #65 #66 #89 #94)

Gerado localmente na retomada do PR. Issues permanecem abertas.

## #63 Emendas CF/1988 1–141

| Critério | Estado | Notas |
| --- | --- | --- |
| Criar matriz por número, data, fonte e situação da coleta, reconciliando a série com catál | **satisfeito** | publicados=141 lacunas=0; Reconciliação detalhada Câmara×Planalto permanece nas pastas de faixa. |
| Recuperar atos integrais ausentes, incluindo dispositivos autônomos, anexos, regras transi | **parcial** | Heurística lexical; emendas de artigo único que só alteram a CF podem não disparar marcadores.; Não extrai somente a redação incorporada à Constituição: cada ar |
| Distinguir claramente emendas da CF/1988, emendas de revisão e emendas de constituições hi | **satisfeito** |  |
| Registrar vínculos da Constituição/ADCT com o ato modificador e seus dispositivos autônomo | **parcial** | Vínculo registrado por citação textual na Constituição consolidada publicada.; Mapa dispositivo-a-dispositivo (ADCT ↔ artigos da emenda) ainda não estruturado. |
| Preservar metadados de edição/fonte/captura, hashes e provas de conversão, sem presumir vi | **parcial** | 79 arquivos antigos da série ainda sem frontmatter YAML no Markdown publicado.; Provas de conversão/hashes das faixas cobrem a recuperação; a matriz unificada n |
| Não recontar Constituição consolidada ou edições alternativas como se fossem emendas colet | **satisfeito** |  |

Resumo: satisfeitos=3 parciais=3 pendentes=0; `issue_fechavel=False`.

## #65 DLG / #66 RSF / #89 RCD / #94 RCN

| Critério transversal | Estado atual |
| --- | --- |
| Catálogo Senado reconciliado com identidade/ID/URL/estado | satisfeito (4 espécies) |
| Coleta integral com retomada e limites de acesso | em progresso (coleta retomável; prioridade RCN) |
| Rejeição de HTML erro/login e falsa íntegra | satisfeito (pipeline + testes) |
| Anexos essenciais bloqueiam publicação | satisfeito (`anexos-pendentes`) |
| Descoberta Câmara RCD pós-1991 | parcial (63 citações nº/ano no Regimento 30ª ed.; íntegras individuais pendentes) |
| Completar Markdown do catálogo | pendente (não parar em 5 amostras) |

Descoberta Câmara: {'citacoes_unicas_numero_ano_pos_1991': 63, 'tambem_no_senado': 0, 'somente_descoberta_camara': 63}. Fonte: `https://bd.camara.leg.br/bd/items/dc8e99ca-5f5c-4e33-8cab-626f82522a8b`.

## Não feito neste passo

- Merge / fechamento de issues
- README agregado / contagens globais
- Íntegra individual de cada RCD citada pós-1991

## Contagens reconciliadas (neste avanço)

| Espécie | Catálogo | Publicado | Anexos pendentes | Identificado não coletado |
| --- | ---: | ---: | ---: | ---: |
| DLG | 15944 | 85 | 0 | 15859 |
| RSF | 6578 | 85 | 0 | 6493 |
| RCD | 1885 | 85 | 0 | 1800 |
| RCN | 88 | 82 | 6 | 0 |

Notas: RCN quase completo (6 anexos pendentes). DLG/RSF/RCD em coleta retomável além das 5 amostras iniciais. Descoberta Câmara RCD pós-1991: 63 citações no Regimento.

