# Atos infralegais SEGES — contratação federal (issue #72)

Lote público de **instruções normativas** e **portaria** no acervo federal, com
espécie `in`/`portaria` e órgão emissor no identificador.

## Publicados (Markdown integral)

| ID | Tema | Fonte |
| --- | --- | --- |
| `br-federal-in-seges-me-2021-07-07-65` | Pesquisa de preços | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-me-no-65-de-7-de-julho-de-2021) |
| `br-federal-in-seges-me-2021-07-08-67` | Dispensa eletrônica | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-me-no-67-de-8-de-julho-de-2021) |
| `br-federal-in-seges-me-2022-09-30-73` | Licitação eletrônica bens/serviços | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-me-no-73-de-30-de-setembro-de-2022) |
| `br-federal-in-seges-2022-08-08-58` | Estudos Técnicos Preliminares | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-no-58-de-8-de-agosto-de-2022) |
| `br-federal-in-seges-me-2022-11-25-81` | Termo de Referência | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-me-no-81-de-25-de-novembro-de-2022) |
| `br-federal-in-seges-mgi-2023-02-07-2` | Alterações (inclui IN 65) | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-mgi-no-2-de-7-de-fevereiro-de-2023) |
| `br-federal-in-seges-mpdg-2017-05-26-5` | Contratação de serviços (execução indireta), edição atualizada | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-no-5-de-26-de-maio-de-2017-atualizada) |
| `br-federal-portaria-seges-me-2021-07-19-8678` | Governança das contratações / PCA | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/portarias/portaria-seges-me-no-8-678-de-19-de-julho-de-2021) |
| `br-federal-in-seges-me-2022-12-26-98` | Autoriza aplicar IN 5/2017 no regime da Lei 14.133 | [Compras.gov.br](https://www.gov.br/compras/pt-br/acesso-a-informacao/legislacao/instrucoes-normativas/instrucao-normativa-seges-me-no-98-de-26-de-dezembro-de-2022) |

## Pendências de inventário (sem falso negativo)

| Tema | Motivo |
| --- | --- |
| Portarias de atualização CATMAT/CATSER | Índice amostrado sem ementa explícita; Plone `@search` HTTP 401; PNCP temática e URL de recomendação CATMAT HTTP 404; página do sistema Catálogo HTTP 200 sem íntegras de portarias de atualização. **Não** se declara inexistência; inventário aberto. |
| DOU da IN 5/2017 | HTTP 403 (WAF) na captura; íntegra publicada a partir do HTML atualizado do portal. CGU Base de Conhecimento oferece PDF integral (138 p.) citado em `fontes.json` sem upload de PDF. |

## Artefatos

- Manifesto: [`metadados/atos-infralegais-seges.json`](../../metadados/atos-infralegais-seges.json)
- Contrato: [`metadados/CONTRATO-atos-infralegais-seges.md`](../../metadados/CONTRATO-atos-infralegais-seges.md)
- Snapshots: `fontes/*.html.xz`
- Verify: `python3 scripts/atos_infralegais_seges.py verify`

## Limites

- Escopo parcial da prioridade da issue #72.
- Edição do portal Compras.gov.br; aviso de não substituição do DOU preservado.
- Decreto 10.947/2022 (PCA/PGC) é espécie decreto e fica fora deste lote.
- Sem certificação de vigência.
