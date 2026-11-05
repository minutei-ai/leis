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

Ver `limites.json` (e `matriz-lote.json`) para publicados vs retidos e pendências de catálogo.

Auditoria integral dos critérios da issue: [`auditoria-criterios-79.md`](auditoria-criterios-79.md).

- 8/8 do lote inicial publicados (6 Constituições + ADCT 1946 + EC 1/1969).
- Séries e vínculos ADCT/`peca_de` e EC1969/`texto_base_relacionado` presentes; demais emendas históricas e edições alternativas ficam pendentes.
- `anexos_no_corpo: 0` nestas capturas HTML não garante ausência de anexos em outras fontes/edições.
