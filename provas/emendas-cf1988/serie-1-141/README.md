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
- a Constituição consolidada / ADCT como substituto do ato modificador.

## Artefato

| Arquivo | Função |
| --- | --- |
| `matriz-serie.json` | Número, data, caminho publicado, fonte e estado de coleta para 1–141 |

As provas de captura e reconversão permanecem nas pastas de faixa. Esta pasta não republica Markdown.

## Reprodução

```bash
python3 scripts/emendas_cf1988_serie_1_141.py build
python3 scripts/emendas_cf1988_serie_1_141.py verify
python3 -m unittest tests.test_emendas_cf1988_serie_1_141 -v
```

## Limites

O acervo não certifica vigência. A presença do arquivo e as citações na Constituição consolidada não substituem o texto autônomo da emenda.
