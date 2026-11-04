# Diagnóstico factual — CTN (Lei 5.172/1966) e SUS (Lei 8.080/1990)

Escopo: só estas duas identidades. CDC, ECA, LGPD, benefícios previdenciários e Lei Maria da Penha ficam fora deste lote.

## O que estava ausente

No acervo público `minutei-ai/leis` (árvore federal conferida na issue #62), não havia arquivo `br-federal-lei-*-5172.md` nem `br-federal-lei-*-8080.md`. Havia decretos e decreto-leis com numeração coincidente (ex.: `br-federal-decreto-2013-08-20-8080.md`, `br-federal-decreto-lei-1943-01-06-5172.md`), que **não** substituem as leis.

Confirmação local antes da publicação (padrão da issue):

```text
5172 → []   # nenhum br-federal-lei-*-5172.md
8080 → []   # nenhum br-federal-lei-*-8080.md
```

## O que o coletor já sabia

No diretório privado de coleta (`/home/yorizel/coletores/leis`, somente leitura para esta publicação):

| Identidade | Catálogo Senado | `coletado_em` do catálogo | Fontes locais | Falha registrada | Markdown no coletor |
| --- | --- | --- | --- | --- | --- |
| `br-federal-lei-1966-10-25-5172` | `catalogos/senado/LEI/1966.json` (senadoId `547034`) | 2026-10-20T22:59:43.866Z | ausente | ausente | ausente |
| `br-federal-lei-1990-09-19-8080` | `catalogos/senado/LEI/1990.json` (senadoId `549956`) | 2026-10-20T22:57:10.115Z | ausente | ausente | ausente |

Pendências no próprio JSON do catálogo anual: **0** para LEI/1966 e LEI/1990. A lacuna **não** é de descoberta de identidade no Senado; as duas normas já constavam do inventário por tipo/ano.

O README do coletor descreve a descoberta federal via API de Dados Abertos do Senado e a obtenção de textos via Portal das Normas (`normas.leg.br`). O relatório `COBERTURA.md` (consulta local 2026-10-23) registra dezenas de milhares de normas identificadas no Senado ainda sem Markdown íntegro. CTN e SUS caem nessa fila: catalogadas, sem captura de texto nem exportação.

Não há evidência, nestes dois casos, de falha pontual gravada em `falhas/` com o `id` canônico; o estado observado é **identificada e ainda não coletada**, não “coletada com erro”.

## Por que a ausência se reproduz sem ação específica

1. O pipeline federal padrão prioriza o catálogo Senado → texto em `normas.leg.br`, não a página compilada/consolidada do Planalto usada nesta recuperação.
2. Contagem de arquivos e presença de leis modificadoras (ex.: LC 227 menciona o CTN) não garantem o texto integral do diploma citado.
3. Sem um gate de cobertura por identidade normativa essencial (área/número/data), a fila genérica pode deixar códigos e leis orgânicas históricas para trás mesmo com URN conhecida.

## O que este lote faz

- Captura oficial Planalto em 2026-11-04T12:08:03Z:
  - CTN compilado: https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm
  - SUS: https://www.planalto.gov.br/ccivil_03/leis/l8080.htm
- Snapshots `.htm.xz`, `fontes.json` (UTC, hashes brutos e de conteúdo sem script F5), Markdown integral, provas de cobertura fonte→Markdown e reconversão offline.
- Não certifica vigência; `fonte_conferencia: nenhuma` (sem segunda fonte oficial nesta entrega).
- Não altera o gerador/manifesto do núcleo de licitações, o README agregado nem a matriz global (integração pelo orquestrador).

## Limites

- Edição Planalto consolidada/compilada ≠ fac-símile do DOU original.
- Sem conferência artigo a artigo com Câmara/Senado nesta entrega.
- Diagnóstico limitado a CTN e SUS; não é censo de todas as lacunas federais.
