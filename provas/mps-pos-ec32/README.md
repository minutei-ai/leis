# Provas — MPs pós-EC 32 (issue #84)

Reconcilia o catálogo `tipo=MPV` do Senado com o acervo, coleta íntegras via normas.leg.br e publica apenas textos sem marcadores `<<ANEXO>>`/`<<TABELA>>`.

```bash
python3 scripts/mps_pos_ec32.py reconcile
python3 scripts/mps_pos_ec32.py fetch --limit 50
python3 scripts/mps_pos_ec32.py build
python3 scripts/mps_pos_ec32.py verify
```

Corte operacional: data ≥ 11/09/2001 e sem campo `reedicao`. Lote histórico: #95.

## Limites deste lote

Ver `limites.json` (e `matriz-publicacao.json`) para publicados vs retidos (anexo/tabela/título) e pendências de catálogo.
