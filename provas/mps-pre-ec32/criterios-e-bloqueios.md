# Critérios e bloqueios — MPs pré-EC 32 (#95)

## Identidade

Série histórica distinta da #84. Chave `numero[-reedicao]` (ex.: `2229-43`).
Corte operacional `data < 2001-09-11` é de descoberta; não afirma vigência nem
resultado parlamentar. Não fundir com a numeração contínua pós-EC 32.
Reedições e complementos mantêm identidades literais separadas
(`revisao-mesmo-numero.json` para coincidências de número).

## Marcadores

Mesmo diagnóstico da #84: `&lt;&lt;ANEXO&gt;&gt;` no HTML normas.leg.br é
placeholder oficial. Recuperação via LexML→Câmara `.doc` quando disponível;
PDF DOU/CLBR permanece retido sem publicar íntegra falsa (snapshot em
`anexos-camara/` + metadados na matriz).

## Estado do lote (esta rodada)

| Métrica | Valor |
|---------|-------|
| Publicados (HTML íntegro ou `.doc` Câmara spliced) | 272 |
| Retidos | 108 |
| Retido PDF layout | 77 |
| Retido sem anexo Câmara | 31 |
| Ausências canônicas no catálogo | ~1900 |
| Presentes no acervo (reconcile) | ~3547 |
| Pré-corte no catálogo | ~6101 |

Fetch retomável ampliou além da amostra inicial (4 → 380+ fontes). Critérios
ainda pendentes: restante do catálogo, reconversão tipográfica dos PDFs,
casos sem anexo digital, integração #70/#83.

Ver `limites.json`, `ausencias.json`, `revisao-mesmo-numero.json`,
`recuperacao-anexos.json`, `diagnostico-marcadores.json`.
