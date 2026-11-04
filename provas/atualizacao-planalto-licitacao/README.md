# Atualização Planalto — Decretos 11.246/11.878 e Leis 12.527/12.462 (issue #93)

Reconversão integral das páginas compiladas do Planalto. O acervo não certifica vigência.

## Conteúdo

- `fontes.json` e `fontes/*.htm.xz` — capturas e hashes
- `reconciliacao-*.json` — cobertura fonte→Markdown e regressões
- `baseline-edicao-anterior.json` — SHA-256 das edições publicadas antes desta atualização
- `manifesto.json` — catálogo do lote, inclusive status da MP 1.349/2026

## MP 1.349/2026

- Situação no Senado: **SEM EFICÁCIA** (PERDA_EFICACIA) em 2026-08-04.
- O Planalto ainda exibe o § 17 do art. 63 da Lei 12.462 com nota da MP 1.349/2026. O Senado/Congresso registra perda de eficácia em 2026-08-04 (SEFICA). O acervo reproduz a compilação do Planalto e registra a perda de eficácia; não certifica vigência residual do § 17 nem reconstrói lei de conversão inexistente.

## Conferência

```bash
/home/yorizel/.local/bin/resource-run --wait python3 scripts/atualizacao_planalto_licitacao.py verify
/home/yorizel/.local/bin/resource-run --wait python3 -m unittest tests.test_atualizacao_planalto_licitacao -v
```
