# Provas — Decretos-leis lacunas (#96)

Preserva `DEL` vs `DEL-mpv` e epígrafes literais divergentes («Decreto nº …»).
Marcadores `<<ANEXO>>` oficiais; anexos Câmara quase sempre PDF (snapshot, sem íntegra falsa).

```bash
python3 scripts/decretos_leis_lacunas.py reconcile
python3 scripts/decretos_leis_lacunas.py fetch          # retomável
python3 scripts/decretos_leis_lacunas.py recover        # .doc se houver; PDF snapshot
python3 scripts/decretos_leis_lacunas.py build
python3 scripts/decretos_leis_lacunas.py verify
```

## Limites deste lote

Ver `limites.json`, `matriz-publicacao.json`, `criterios-e-bloqueios.md`.
Número coincidente → revisão, sem reescrita automática de arquivo existente.
