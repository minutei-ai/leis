# Provas — MPs pós-EC 32 (issue #84)

Reconcilia o catálogo `tipo=MPV` do Senado com o acervo, coleta íntegras via normas.leg.br e recupera anexos da Câmara quando o HTML traz placeholder `<<ANEXO>>`/`<<TABELA>>` (peça real ausente no HTML, não bug do conversor).

```bash
python3 scripts/mps_pos_ec32.py reconcile
python3 scripts/mps_pos_ec32.py fetch          # retomável
python3 scripts/mps_pos_ec32.py recover        # anexos .doc Câmara
python3 scripts/mps_pos_ec32.py build
python3 scripts/mps_pos_ec32.py verify
```

Corte operacional: data ≥ 11/09/2001 e sem campo `reedicao`. Lote histórico: #95.
Ver `limites.json`, `diagnostico-marcadores.json`, `descoberta-camara-anexos.json`.
