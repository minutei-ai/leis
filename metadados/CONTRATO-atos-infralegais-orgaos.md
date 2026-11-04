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

## Regras

1. Sem vigência inferida (`vigencia_certificada: false`).
2. Registro de fontes oficiais por órgão em `catalogo_orgaos`, com o que ainda
   não foi inventariado.
3. Estado de acesso explícito: shell SPA / JS / HTTP de erro **não** vira
   “inexistente”.
4. Markdown integral inclui anexos, tabelas e fac-símiles normativos; imagem com
   conteúdo jurídico não é omitida como brasão.
5. Modos original / consolidada / multivigente da fonte, quando existirem, são
   identidades distintas — não concatenar.
6. Escopo parcial: três exemplos da issue #75; não declara cobertura nacional.
7. Separar atos normativos de notícias, consultas e atos individuais quando a
   fonte os mistura.

## Edições SIJUT / DOU neste lote

- RFB IN 2.110: visões `original` e `vigente` em Markdown distintos; `multivigente` só em snapshot JSON.
- CMN 4.966: edição original do DOU; consolidada do portal BCB permanece bloqueada por shell JS (pendência residual, sem falso negativo).
- RDC 50: tabelas pesquisáveis no Markdown; diagrama como fac-símile normativo adicional.
