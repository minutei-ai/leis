# Diagnóstico factual — Lei 8.213/1991 e Lei 11.340/2006

Escopo: só estas duas identidades. CDC, ECA, CTN e SUS ficam fora deste lote (outros responsáveis).

## O que estava ausente

No acervo público `minutei-ai/leis` (árvore federal conferida na issue #62), não havia arquivo `br-federal-lei-*-8213.md` nem `br-federal-lei-*-11340.md`. Havia decretos e decreto-leis com numeração coincidente (ex.: `br-federal-decreto-2014-03-21-8213.md`, `br-federal-decreto-lei-1945-11-23-8213.md`), que **não** substituem as leis.

Confirmação local antes da publicação (padrão da issue):

```text
8213 → []   # nenhum br-federal-lei-*-8213.md
11340 → []  # nenhum br-federal-lei-*-11340.md
```

## O que o coletor já sabia

No diretório privado de coleta (`/home/yorizel/coletores/leis`, somente leitura para esta publicação):

| Identidade | Catálogo Senado | `coletado_em` do catálogo | Fontes locais | Falha registrada com o id canônico | Markdown no coletor |
| --- | --- | --- | --- | --- | --- |
| `br-federal-lei-1991-07-24-8213` | `catalogos/senado/LEI/1991.json` (senadoId `550089`) | 2026-10-20T22:57:08.362Z | ausente | ausente | ausente |
| `br-federal-lei-2006-08-07-11340` | `catalogos/senado/LEI/2006.json` (senadoId `572125`) | 2026-10-20T22:56:45.952Z | ausente | ausente | ausente |

Pendências no próprio JSON do catálogo anual: **0** para LEI/1991 e LEI/2006. A lacuna **não** é de descoberta de identidade no Senado; as duas normas já constavam do inventário por tipo/ano.

O README do coletor descreve a descoberta federal via API de Dados Abertos do Senado e a obtenção de textos via Portal das Normas (`normas.leg.br`). O relatório `COBERTURA.md` registra dezenas de milhares de normas identificadas no Senado ainda sem Markdown íntegro. Benefícios previdenciários e Lei Maria da Penha caem nessa fila: catalogadas, sem captura de texto nem exportação.

Não há evidência, nestes dois casos, de falha pontual gravada em `falhas/` com o `id` canônico federal; o estado observado é **identificada e ainda não coletada**, não “coletada com erro”. Falhas com número coincidente referem-se a normas estaduais/municipais ou decretos distintos.

## Por que a ausência se reproduz sem ação específica

1. O pipeline federal padrão prioriza o catálogo Senado → texto em `normas.leg.br`, não a página consolidada do Planalto (`l8213cons.htm`) nem a norma atualizada da Câmara usadas nesta recuperação.
2. Contagem de arquivos e presença de leis modificadoras ou de citações a esses diplomas em outros documentos não garantem o texto integral do diploma citado.
3. Sem um gate de cobertura por identidade normativa essencial (área/número/data), a fila genérica pode deixar códigos e leis orgânicas históricas para trás mesmo com URN conhecida.

## O que este lote faz

- Captura oficial em 2026-11-04T12:22:09Z:
  - Lei 8.213 consolidada: https://www.planalto.gov.br/ccivil_03/leis/l8213cons.htm
  - Lei 11.340 norma atualizada: https://www2.camara.leg.br/legin/fed/lei/2006/lei-11340-7-agosto-2006-545133-normaatualizada-pl.html
- Snapshots `.xz`, `fontes.json` (UTC, hashes brutos e de conteúdo sem script F5 quando aplicável), Markdown integral, provas de cobertura fonte→Markdown e reconversão offline.
- Não certifica vigência; `fonte_conferencia: nenhuma` (sem segunda fonte oficial nesta entrega).
- Não altera o gerador/manifesto do núcleo de licitações, o README agregado nem a matriz global (integração pelo orquestrador).

## Limites

- Edição Planalto consolidada / Câmara atualizada ≠ fac-símile do DOU original.
- Sem conferência artigo a artigo com a outra casa (Câmara↔Planalto) nesta entrega.
- A página da Câmara não traz o rodapé canônico “Este texto não substitui o publicado no DOU…”.
- Diagnóstico limitado a Lei 8.213 e Lei 11.340; não é censo de todas as lacunas federais.
