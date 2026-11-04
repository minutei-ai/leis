# Critérios e bloqueios — MPs pós-EC 32 (#84)

## Diagnóstico dos marcadores

Os literais `<<ANEXO>>` / `<<TABELA>>` / `<<ANEXOS>>` no Markdown convertido
vêm de placeholders oficiais no HTML de normas.leg.br, escapados como
`&lt;&lt;ANEXO&gt;&gt;`. Não são gerados por `convert_html`.

Em 189 capturas retidas por marcador (lote inicial):

- placeholder no fim do HTML, sem peça embutida;
- republicações/retificações alternativas em normas.leg.br quase nunca trazem o anexo
  (a «Republicação Integral» da MP 45/2002 omite o marcador **e** o anexo — não publicar
  como íntegra);
- Planalto (`planalto.gov.br`) resetou conexão neste host (2026-11-04); indisponibilidade
  HTTP **não** afirma ausência da norma nem vigência.

## Recuperação Câmara (LexML → norma-pe)

| Resultado | Quantidade (após recover) | Ação |
|-----------|---------------------------|------|
| `.doc` convertido com cobertura | 48 | Publicado com anexos no corpo |
| Somente `.pdf` (fac-símile DOU / layout) | 128 | Snapshot em `anexos-camara/`; **não** OCR como íntegra |
| Sem anexo na ficha Câmara | 13 | Retido; peça ainda ausente nas fontes digitais usadas |
| Título não casado | 1 | Retido |

Critério de publicação com anexo: LibreOffice `.doc`→HTML → `convert_html` → splice
no lugar do placeholder → `coverage_safe` fonte→Markdown. PDF multicoluna fica
pendente de reconversão tipográfica confiável.

## Estado do lote (esta rodada)

| Métrica | Valor |
|---------|-------|
| Publicados | 57 |
| Retidos | 142 |
| `.doc` Câmara recuperados e publicados | 48 |
| PDF layout pendente (snapshot capturado) | 128 |
| Sem anexo Câmara | 13 |
| Título não casado | 1 |

## Critérios completos (issue #84)

- [x] Reconciliar catálogo Senado pós-corte sem reedição × acervo
- [x] Coletar HTML normas.leg.br das ausências canônicas (199 capturas no lote)
- [x] Diagnosticar marcadores (placeholder oficial vs bug)
- [x] Recuperar anexos `.doc` Câmara e publicar com cobertura
- [x] Capturar snapshots PDF Câmara sem publicar íntegra falsa
- [ ] Reconverter 128 PDFs Câmara com fidelidade tipográfica
- [ ] Completar 13 sem anexo Câmara + 1 título + lacunas ainda sem fetch se o catálogo crescer
- [ ] Situação parlamentar / conversão / eficácia por vínculo documentado (não por HTTP)
- [ ] Integração filtros #70 / rastreador #83 (outro lote)

Ver `limites.json`, `diagnostico-marcadores.json`, `descoberta-camara-anexos.json`,
`recuperacao-anexos.json`.
