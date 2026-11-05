# Critérios e bloqueios — decretos-leis (#96)

## Identidade e epígrafes

- Preservar `DEL` vs `DEL-mpv` sem fusão de documentos.
- Número coincidente em outra data/série → revisão (`revisao-mesmo-numero.json`),
  sem reescrever arquivo existente.
- Epígrafe literal «Decreto nº …» quando a fonte assim apresenta, com nota de
  divergência; sem correção editorial para «Decreto-Lei».

## Marcadores / anexos

Placeholders `&lt;&lt;ANEXO&gt;&gt;` oficiais (muitas vezes remissão a volumes
CLBR). Anexos Câmara quase sempre `.pdf` (fac-símile); capturados em
`anexos-camara/` com hash, **não** publicados como Markdown até reconversão
tipográfica confiável. URLs e status na descoberta LexML / matriz.

## Estado do lote (esta rodada)

| Métrica | Valor |
|---------|-------|
| Publicados (HTML íntegro sem marcador) | 124 |
| Retidos | 56 |
| Retido PDF layout | 20 |
| Retido sem anexo Câmara | 36 |
| Ausências canônicas | 738 |
| Catálogo Senado (DEL + DEL-mpv) | 12378 (9 DEL-mpv) |

Fetch retomável ampliou além da amostra (58 → 180+ fontes). Pendências:
restante das 738 ausências, reconversão PDF, integração #70/#83.

Ver `limites.json`, `ausencias.json`, `revisao-mesmo-numero.json`,
`recuperacao-anexos.json`, `diagnostico-marcadores.json`.
