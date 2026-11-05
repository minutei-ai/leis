# LC 115/2002, LC 147/2014 e LC 1/1962 (issue #68)

Publicação das duas LCs ausentes do acervo e reconciliação da identidade histórica da LC 1/1962, distinta da LC 1/1967 já publicada.

## Conteúdo

- `reconciliacao-identidades.json` — reconciliação integral das 240 linhas do snapshot oficial (ID Senado, URL, campos/aliases originais, estado de caminho e caminho publicado)
- `fontes/` — snapshots Senado (115/147 original) e Planalto (LC 1/1962; LC 147 com anexo)
- Markdown em `federal/` com cabeçalho de metadados; `situacao=nao-informada`; `vigencia_certificada=false`

## Identidades

| Norma | `id` | Estado |
| --- | --- | --- |
| LC 115/2002 | `br-federal-lei-complementar-2002-12-26-115` | publicado (Senado; Anexo no corpo) |
| LC 147/2014 | `br-federal-lei-complementar-2014-08-07-147` | publicado (Planalto com Anexo Único; Senado original incompleto nas tabelas) |
| LC 1/1962 | `br-federal-lei-complementar-1962-07-17-1` | publicado (Planalto Lcp01-62.htm); senadoId 30812083 |
| LC 1/1967 | `br-federal-lei-complementar-1967-11-09-1` | já publicado; não fundido com 1962 |

## Escopo da reconciliação e provas

A captura fixada contém 240 registros LCP. Cada identidade foi associada a um arquivo por tipo, número textual (inclui complemento) e data de assinatura; o inventário registra as 240 correspondências, sem duplicar caminhos. Isso prova apenas a correspondência do nome canônico com o catálogo desta captura, não a correção de todas as epígrafes, a integridade dos 240 textos, a vigência nem a cobertura do universo histórico brasileiro. Os campos de aliases e denominação do catálogo ficam preservados linha a linha.

A prova de reconversão compara os corpos dos snapshots oficiais com o Markdown para LC 115/2002, LC 147/2014 (incluindo Anexo Único) e LC 1/1962. Para LC 115, somente o marcador de catálogo e o marcador literal `<<anexo>>` são excluídos; o título, a ementa e o bloco `ANEXO` são comparados. Os demais textos da captura não recebem estado de conversão revalidada por esta entrega. Não se certifica vigência e LC 1/1962 permanece distinta da LC 1/1967.

## Conferência

```bash
/home/yorizel/.local/bin/resource-run --wait python3 -m unittest tests.test_lc_complementares_68 -v
```
