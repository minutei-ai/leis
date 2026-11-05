# Atos infralegais SEGES — contratação federal (issue #72)

Lote público de **instruções normativas** e **portarias** no acervo federal, com
espécie `in`/`portaria` e órgão emissor no identificador.

## Publicados (Markdown integral)

| ID | Tema | Fonte |
| --- | --- | --- |
| `br-federal-in-seges-me-2021-07-07-65` | Pesquisa de preços | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-me-no-65-de-7-de-julho-de-2021) |
| `br-federal-in-seges-me-2021-07-08-67` | Dispensa eletrônica | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-me-no-67-de-8-de-julho-de-2021) |
| `br-federal-in-seges-me-2022-09-30-73` | Licitação eletrônica bens/serviços | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-me-no-73-de-30-de-setembro-de-2022) |
| `br-federal-in-seges-2022-08-08-58` | Estudos Técnicos Preliminares | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-no-58-de-8-de-agosto-de-2022) |
| `br-federal-in-seges-me-2022-11-25-81` | Termo de Referência | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-me-no-81-de-25-de-novembro-de-2022) |
| `br-federal-in-seges-mgi-2023-02-07-2` | Alterações (inclui IN 65); órgão literal SEGES/MGI | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-mgi-no-2-de-7-de-fevereiro-de-2023) |
| `br-federal-in-seges-mpdg-2017-05-26-5` | Contratação de serviços (execução indireta), edição atualizada com anexos | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-no-5-de-26-de-maio-de-2017-atualizada) |
| `br-federal-portaria-seges-me-2021-07-19-8678` | Governança das contratações (PCA é um dos instrumentos; ≠ regulamento PCA/PGC) | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/portarias/portaria-seges-me-no-8-678-de-19-de-julho-de-2021) |
| `br-federal-in-seges-me-2022-12-26-98` | Autoriza aplicar IN 5/2017 no regime da Lei 14.133 | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-me-no-98-de-26-de-dezembro-de-2022) |
| `br-federal-portaria-seges-me-2022-02-02-938` | Catálogo eletrônico de padronização (≠ CATMAT/CATSER; ≠ PCA/PGC) | [DOU](https://www.in.gov.br/web/dou/-/portaria-seges/me-n-938-de-2-de-fevereiro-de-2022-377800503) |

## Classificação crítica (Portaria 8.678)

A Portaria SEGES/ME 8.678/2021 **dispõe sobre a governança das contratações públicas**. O texto literal inclui o Plano de Contratações Anual como um dos instrumentos (arts. 2º, VI, 6º e 10). Isso **não** a torna o regulamento do PCA/PGC: esse papel cabe ao **Decreto 10.947/2022** (espécie decreto, já no acervo).

## Inventário CATMAT/CATSER/PCA

Arquivo: [`inventario-portarias-catalogo-pca.json`](inventario-portarias-catalogo-pca.json)

- Índices oficiais de portarias **vigentes** e **revogadas** percorridos com **paginação completa** (não amostra).
- Nenhum título/ementa nos índices com literal “atualização CATMAT/CATSER”.
- Portaria 938/2022 recuperada no DOU (portal Compras: conteúdo restrito).
- FAQ do PNCP distingue catálogo eletrônico de padronização do sistema CATMAT/CATSER.
- Sem falso negativo: inventário registra o que os catálogos oficiais listam.

## Integridade IN 5/2017

Arquivo: [`integridade-anexos-in5-2017.json`](integridade-anexos-in5-2017.json)

Conjunto de anexos do Markdown = conjunto do HTML do portal (I–XII-A, inclusive III revogado com riscado e VIII-A). Notas de alteração/revogação preservadas. PDF CGU (138 p.) citado em `fontes.json` sem upload.

## Pendências de inventário (sem falso negativo)

| Tema | Motivo |
| --- | --- |
| Portarias operacionais de atualização CATMAT/CATSER fora dos índices | Índices paginados sem ementa literal; sistema Catálogo HTTP 200 sem lista normativa; orientação 36 HTTP 404. Inventário aberto para atos fora desses catálogos. |
| DOU da IN 5/2017 | HTTP 403 (WAF) na captura; íntegra publicada a partir do HTML atualizado do portal. |

## Artefatos

- Manifesto: [`metadados/atos-infralegais-seges.json`](../../metadados/atos-infralegais-seges.json)
- Contrato: [`metadados/CONTRATO-atos-infralegais-seges.md`](../../metadados/CONTRATO-atos-infralegais-seges.md)
- Snapshots: `fontes/*.html.xz`
- Verify: `python3 scripts/atos_infralegais_seges.py verify`

## Limites

- Escopo parcial da prioridade da issue #72.
- Edições do portal Compras.gov.br ou DOU conforme a fonte de cada ato; aviso de não substituição do DOU/versão certificada preservado.
- Decreto 10.947/2022 (PCA/PGC) é espécie decreto e fica fora deste lote (já publicado no acervo).
- Sem certificação de vigência.
