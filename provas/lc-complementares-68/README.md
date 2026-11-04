# LC 115/2002, LC 147/2014 e LC 1/1962 (issue #68)

Publicação das duas LCs ausentes do acervo e reconciliação da identidade histórica da LC 1/1962, distinta da LC 1/1967 já publicada.

## Conteúdo

- `reconciliacao-identidades.json` — catálogo de reconciliação (ID Senado, URL, estado, caminho)
- `fontes/` — snapshots HTML/dados das publicações originais (Senado) e do Planalto (LC 1/1962); lista LCP capturada
- Markdown publicado em `federal/` no padrão do acervo (corpo sem YAML do coletor)

## Identidades

| Norma | `id` | Estado |
| --- | --- | --- |
| LC 115/2002 | `br-federal-lei-complementar-2002-12-26-115` | publicado (Senado/normas.leg.br) |
| LC 147/2014 | `br-federal-lei-complementar-2014-08-07-147` | publicado (Senado/normas.leg.br) |
| LC 1/1962 | `br-federal-lei-complementar-1962-07-17-1` | publicado (Planalto Lcp01-62.htm); senadoId 30812083 |
| LC 1/1967 | `br-federal-lei-complementar-1967-11-09-1` | já publicado; não fundido com 1962 |

## Conferência

```bash
/home/yorizel/.local/bin/resource-run --wait python3 -m unittest tests.test_lc_complementares_68 -v
```

Limites: a lista LCP do Senado é catálogo vivo (hash desta captura ≠ hash citado na issue); não certifica vigência nem cobertura de todas as LCs históricas.
