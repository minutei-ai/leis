# Diagnóstico factual — omissão CDC e ECA na coleta federal

Conferência local em 2026-11-04, sobre o commit-base `d4e425a57f1c1e1ee9f770e7bc7e673264a2ed58`
(`origin/main`) e o diretório privado de coleta `/home/yorizel/coletores/leis`
(leitura apenas; sem instalar, copiar cache ou targets).

## Identidades no catálogo do Senado

Ambas constam do inventário `catalogos/senado/LEI/1990.json`:

| Norma | `id` canônico | `senadoId` | URN |
| --- | --- | --- | --- |
| Lei 8.078/1990 (CDC) | `br-federal-lei-1990-09-11-8078` | `549954` | `urn:lex:br:federal:lei:1990-09-11;8078` |
| Lei 8.069/1990 (ECA) | `br-federal-lei-1990-07-13-8069` | `549945` | `urn:lex:br:federal:lei:1990-07-13;8069` |

## Estado no coletor privado e no acervo público

- Em `coletores/leis/federal/` **não** havia Markdown dessas identidades.
- Em `coletores/leis/fontes/senado/` **não** havia arquivos `br-federal-lei-1990-09-11-8078*` nem `br-federal-lei-1990-07-13-8069*`.
- Em `coletores/leis/falhas/` **não** havia recibo de falha com esses `id` (buscas por nome de arquivo e por conteúdo).
- No acervo público (`federal/`), busca por `br-federal-lei-…-8078` / `…-8069` e por aliases
  (“Código de Defesa do Consumidor”, “Estatuto da Criança…”) na árvore de leis de 1990:
  **nenhum** arquivo correspondente. Havia decretos e outras espécies com numeração
  coincidente, que não são essas leis.

## Cobertura do ano no catálogo LEI

Medição sobre `catalogos/senado/LEI/*.json` × existência de `federal/<id>.md` no coletor:

| Ano LEI | Identificadas no catálogo | Com Markdown local | Sem Markdown |
| ---: | ---: | ---: | ---: |
| 1990 | 166 | 0 | 166 |
| 1991 | 238 | 0 | 238 |
| (referência) 2015 | 163 | 163 | 0 |

O ano **1990** do tipo LEI está inteiro sem Markdown íntegro no coletor. CDC e ECA
estão nesse conjunto. Não há evidência, nestes dois casos, de filtro por identidade
nem de falha registrada: as identidades constam do catálogo e simplesmente ainda
não foram processadas até gerar `federal/`, `fontes/<id>.json` e arquivo HTML gzip.

O coletor `scripts/collect-senado.ts` só grava norma quando conclui download +
conversão; com `intact(id)` falso e sem `falhas/<id>.json`, a próxima execução
ainda pode alcançá-las. A lacuna publicada reflete o backlog de coleta LEI do
Senado (COBERTURA.md do coletor: dezenas de milhares de normas catalogadas sem
Markdown íntegro), não ausência no catálogo oficial consultado.

## O que este lote faz

Publica CDC e ECA a partir das fontes oficiais do Planalto indicadas na issue #62,
com conferência da Câmara, provas e verificação próprias — fora do pipeline de
licitações. Não declara que a coleta federal do Senado esteja corrigida para o
ano 1990 inteiro.
