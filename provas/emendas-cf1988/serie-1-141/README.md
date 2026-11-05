# Provas — Emendas CF/1988, série 1–141

Consolidação da cobertura do issue [#63](https://github.com/minutei-ai/leis/issues/63) após os lotes de faixa já mesclados:

- [PR #91](https://github.com/minutei-ai/leis/pull/91) — faixa 001–050
- [PR #92](https://github.com/minutei-ai/leis/pull/92) — faixa 051–100
- [PR #97](https://github.com/minutei-ai/leis/pull/97) — faixa 101–141

## Escopo

Textos autônomos das Emendas Constitucionais nº 1 a 141 à Constituição de 1988.

Fora do escopo desta matriz:

- emendas constitucionais de revisão;
- emendas a constituições históricas (data &lt; 1988);
- a Constituição consolidada / ADCT como substituto do ato modificador;
- mapa artigo-a-artigo de toda a CF (o issue exige vínculos CF/ADCT → ato/dispositivos autônomos).

## Artefatos

| Arquivo | Função |
| --- | --- |
| `matriz-serie.json` | Número, data, caminho publicado, fonte, estado de coleta e vínculos |
| `matriz-criterios-aceite.json` | Estado de cada critério de aceite do #63 (contagem ≠ fechamento) |
| `mapa-constituicao-adct-dispositivos.json` | Mapa CF/ADCT → ato e dispositivos (escopo literal do issue) |
| `manifesto-frontmatter.json` | Frontmatter contrato acrescentado aos 79 MD sem metadados |

As provas de captura e reconversão permanecem nas pastas de faixa.

## Reprodução

```bash
python3 scripts/emendas_cf1988_serie_1_141.py ensure-frontmatter
python3 scripts/emendas_cf1988_serie_1_141.py build
python3 scripts/emendas_cf1988_serie_1_141.py verify
python3 -m unittest tests.test_emendas_cf1988_serie_1_141 -v
```

## Limites

O acervo não certifica vigência. A presença do arquivo e as citações na Constituição consolidada não substituem o texto autônomo da emenda. A contagem 141/141 é necessária e insuficiente: `issue_fechavel` permanece `false`. Captura original desconhecida nos lotes pré-metadados fica explícita (`desconhecido`), sem atribuição retroativa de hash.
