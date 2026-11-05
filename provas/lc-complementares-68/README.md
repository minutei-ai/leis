# LC 115/2002, LC 147/2014 e LC 1/1962 (issue #68)

Publicação das duas LCs ausentes do acervo e reconciliação da identidade histórica da LC 1/1962, distinta da LC 1/1967 já publicada.

## Conteúdo

- `reconciliacao-identidades.json` — reconciliação integral das 240 linhas do snapshot oficial (ID Senado, URL, campos/aliases originais, estado de caminho e caminho publicado)
- `fontes/` — snapshots Senado (115/147 original), Planalto (LC 1/1962; LC 147 com anexo) e Câmara (publicação original e retificação LC 1/1962)
- Markdown em `federal/` com cabeçalho de metadados; `situacao=nao-informada`; `vigencia_certificada=false`

## Identidades

| Norma | `id` | Estado |
| --- | --- | --- |
| LC 115/2002 | `br-federal-lei-complementar-2002-12-26-115` | publicado (Senado; Anexo no corpo) |
| LC 147/2014 | `br-federal-lei-complementar-2014-08-07-147` | publicado (Planalto com Anexo Único; Senado original incompleto nas tabelas) |
| LC 1/1962 | `br-federal-lei-complementar-1962-07-17-1` | publicado (Planalto Lcp01-62.htm; retificação DOU 24/07/1962 preservada em edição própria); senadoId 30812083 |
| LC 1/1967 | `br-federal-lei-complementar-1967-11-09-1` | já publicado; não fundido com 1962 |

## Escopo da reconciliação e provas

A captura fixada contém 240 registros LCP. Cada identidade foi associada a um arquivo por tipo, número textual (inclui complemento) e data de assinatura; o inventário registra as 240 correspondências, sem duplicar caminhos. Isso prova apenas a correspondência do nome canônico com o catálogo desta captura, não a correção de todas as epígrafes, a integridade dos 240 textos, a vigência nem a cobertura do universo histórico brasileiro. Os campos de aliases e denominação do catálogo ficam preservados linha a linha.

A prova de reconversão compara os corpos dos snapshots oficiais com o Markdown para LC 115/2002, LC 147/2014 (incluindo Anexo Único) e LC 1/1962. Para LC 115, somente o marcador de catálogo e o marcador literal `<<anexo>>` são excluídos; o título, a ementa e o bloco `ANEXO` são comparados. Os demais textos da captura não recebem estado de conversão revalidada por esta entrega. Não se certifica vigência e LC 1/1962 permanece distinta da LC 1/1967.

### LC 1/1962: publicação original, retificação e edição Planalto

As capturas integrais oficiais da Câmara preservam separadamente a publicação original no DOU de 17/07/1962, p. 7597 (`fontes/camara-lcp01-62-publicacao-original.html.xz`) e a retificação no DOU de 24/07/1962, p. 7837 (`fontes/camara-lcp01-62-retificacao.html.xz`). A página de dados da norma registra literalmente “Publicada no DO como Lei Complementar ao Ato Adicional”; esse rótulo é a série histórica registrada para 1962 e não é inferido do ano. A LC 1/1967 permanece identidade distinta e sua série histórica segue `desconhecido`.

Links oficiais: [dados da norma](https://www2.camara.leg.br/legin/fed/leicom/1960-1969/leicomplementar-1-17-julho-1962-541564-norma-pl.html), [publicação original](https://www2.camara.leg.br/legin/fed/leicom/1960-1969/leicomplementar-1-17-julho-1962-541564-publicacaooriginal-46773-pl.html), [retificação](https://www2.camara.leg.br/legin/fed/leicom/1960-1969/leicomplementar-1-17-julho-1962-541564-retificacao-46775-pl.html), [retificação no Planalto](https://www.planalto.gov.br/ccivil_03/leis/lcp/ret/retlcp01-62.htm). As capturas Câmara têm SHA-256 e instante UTC no objeto LC 1/1962 de `fontes.json`.

A retificação aparece como edição própria [`federal/edicoes/br-federal-lei-complementar-1962-07-17-1-retificacao-1962-07-24.md`](../../federal/edicoes/br-federal-lei-complementar-1962-07-17-1-retificacao-1962-07-24.md), relacionada à mesma `norma_id` e com `edicao_id` próprio. Ela manda inserir “O Presidente da República” após a ementa e excluir a ocorrência duplicada “O congresso Nacional decreta:” após o preâmbulo. O snapshot Planalto capturado em 04/11/2026 contém a fórmula “O Presidente da República Faço saber que o Congresso Nacional decreta…” e não contém a duplicação indicada. A comparação não altera a publicação original nem funde as edições.

Para LC 115/2002, LC 147/2014 e LC 1/1962, `orgao_emissor=Congresso Nacional` vem da fórmula literal de promulgação nas respectivas capturas (`Congresso Nacional decreta e eu sanciono`). `fonte_orgao` fica como o Senado ou Planalto que serviu a edição/captura. A exportação BM25 preserva esse papel e permite combinar `serie_historica`, número e data. LC 115/147 e LC 1/1967 têm série histórica desconhecida onde as fontes verificadas não dão rótulo.

## Conferência

```bash
/home/yorizel/.local/bin/resource-run --wait python3 -m unittest tests.test_lc_complementares_68 -v
```
