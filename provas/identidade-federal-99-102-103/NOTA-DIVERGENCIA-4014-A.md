# Divergência literal — Decreto-Lei 4.014-A / cabeçalho Senado 1.014-A

## Identidade

| Campo | Valor |
| --- | --- |
| Caminho no acervo | `federal/br-federal-decreto-lei-1942-01-13-4014-a.md` |
| Catálogo Senado | `DEL-4014-A-1942-01-13`, senadoId [529102](https://legis.senado.leg.br/norma/529102), `numero=4014`, `complemento=A` |
| LexML | `urn:lex:br:federal:decreto.lei:1942-01-13;4014-a` |
| Câmara | [DECRETO-LEI Nº 4.014-A, DE 13 DE JANEIRO DE 1942](https://www2.camara.leg.br/legin/fed/declei/1940-1949/decreto-lei-4014-a-13-janeiro-1942-414027-publicacaooriginal-1-pe.html) |
| Ementa (todas as fichas) | Cria o Destacamento Misto de Guarnição com sede em Fernando de Noronha |

O DEL 4014 **sem** complemento A é outro registro (senadoId 529101), sobre despachantes aduaneiros.

## Cabeçalhos literais colacionados (2026-11-04)

**Câmara — publicação original** (snapshot `fontes/br-federal-decreto-lei-1942-01-13-4014-a.html.xz`):

```text
DECRETO-LEI Nº 4.014-A, DE 13 DE JANEIRO DE 1942
```

**Senado — publicação textual** (`divergencias/senado-529102-publicacao-15820792.html.xz`, URL https://legis.senado.leg.br/norma/529102/publicacao/15820792):

```text
DECRETO-LEI N. 1.014-A - DE 13 DE JANEIRO DE 1942
```

O corpo (artigos, ementa, assinaturas) é o mesmo Destacamento de Fernando de Noronha nas duas casas. A divergência está no **número impresso no cabeçalho** da publicação textual do Senado (`1.014-A` vs `4.014-A`).

## Decisão de publicação

- O Markdown do acervo publica a forma **4.014-A** da Câmara, alinhada ao caminho, ao catálogo Senado/LexML e à ementa.
- A forma **1.014-A** do Senado é preservada como evidência de divergência da própria fonte, sem reescrita silenciosa do HTML senatorial.
- Testes deste lote exigem `4.014-A` / Fernando de Noronha no Markdown publicado; não forçam equivalência cega título≡caminho em todo o federal (ver issue #102).
