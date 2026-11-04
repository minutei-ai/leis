# Contrato — atos infralegais por órgão (issue #75)

Lote `atos-infralegais-orgaos`: inventário inicial de normas infralegais de
ANVISA, Receita Federal e CMN/BCB.

## Espécie e identidade

| Espécie (`norma_tipo`) | Padrão de id |
| --- | --- |
| `rdc` | `br-federal-rdc-<orgao>-<AAAA-MM-DD>-<numero>` |
| `in` | `br-federal-in-<orgao>-<AAAA-MM-DD>-<numero>` |
| `resolucao-cmn` | `br-federal-resolucao-cmn-<AAAA-MM-DD>-<numero>` |

Órgão e espécie fazem parte da chave. Resolução CMN, Resolução BCB e Comunicado
com o mesmo número **não** são intercambiáveis.

## Regras (oito critérios da issue #75)

1. Sem vigência inferida (`vigencia_certificada: false`).
2. Registro de fontes oficiais por órgão/espécie em `catalogo_orgaos`, com o que
   ainda não foi inventariado.
3. Catálogo com paginação/período, IDs oficiais e estados de acesso em
   `provas/atos-infralegais-orgaos/catalogos-orgaos-paginacao.json`. Shell SPA /
   JS / HTTP de erro / lista vazia com `quantidadeTotal` **não** vira
   “inexistente”.
4. Identidade com órgão emissor e espécie (`norma_tipo` + padrão de id).
   Resolução CMN, Resolução BCB e Comunicado com o mesmo número não são
   intercambiáveis.
5. Markdown integral inclui anexos, tabelas e fac-símiles normativos; imagem com
   conteúdo jurídico não é omitida como brasão.
6. Modos original / consolidada / multivigente da fonte, quando existirem, são
   identidades distintas — não concatenar. Prova em
   `diferencas-edicoes-rfb-cmn.json`.
7. Alterações, revogações e efeitos com evidência literal e `desconhecidos`
   explícitos em `relacoes` (compatível com #70).
8. Separar atos normativos de notícias, consultas públicas, propostas e atos
   individuais (`classificacao-fontes-orgaos.json`). Escopo parcial: três lotes
   da issue; não declara cobertura nacional.

## Edições SIJUT / DOU neste lote

- RFB IN 2.110 (`idAto` 126687): path `/visao/original` devolve payload
  `visao=conjunta` (literal SIJUT); Markdown distinto da visão `vigente`;
  `multivigente` só em snapshot JSON. Histórico SIJUT registra INs 2185/2289/2321.
- CMN 4.966: edição **original** do DOU publicada; consolidada do portal BCB
  permanece bloqueada por shell JS. DOU original **não** equivale à consolidada
  BCB (pendência residual, sem falso negativo).
- RDC 50: tabelas pesquisáveis no Markdown; diagrama como fac-símile normativo
  adicional.
