# Provas — Constituições históricas, ADCT 1946 e EC 1/1969

Lote do issue [#79](https://github.com/minutei-ai/leis/issues/79).

## Escopo

- Constituições de 1824, 1891, 1934, 1937, 1946 e 1967 (publicação original Câmara).
- ADCT de 1946 como peça identificada da mesma edição.
- EC 1/1969 como ato modificador da série de 1967 (normas.leg.br / Senado).

## Reprodução

```bash
python3 scripts/historico_constitucional.py fetch
python3 scripts/historico_constitucional.py build
python3 scripts/historico_constitucional.py verify
python3 -m unittest tests.test_historico_constitucional -v
```

O acervo **não certifica vigência**. Divergências de data Câmara×Senado estão em `catalogo-lote.json` / notas de edição.

## Limites deste lote

Ver `limites.json` (e `matriz-publicacao.json`) para publicados vs retidos (anexo/tabela/título) e pendências de catálogo.
