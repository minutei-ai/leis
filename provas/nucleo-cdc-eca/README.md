# Provas do lote CDC/ECA

Geradas por [`scripts/nucleo_cdc_eca.py`](../../scripts/nucleo_cdc_eca.py). Não editar à mão.

| Arquivo | Função |
| --- | --- |
| `fontes/` | Snapshots oficiais (HTML em `.xz`). |
| `fontes.json` | URL, data UTC, status HTTP, hashes e cabeçalhos de cada captura. |
| `reconciliacao-br-federal-lei-1990-09-11-8078.json` | Cobertura Planalto↔Markdown e conferência artigo a artigo com a Câmara (CDC). |
| `reconciliacao-br-federal-lei-1990-07-13-8069.json` | Idem para o ECA. |
| `diagnostico-coleta-cdc-eca.md` | Evidência factual da omissão destas duas leis na coleta federal. |
| `ferramentas.json` | Versões usadas na geração. |

## Verificar (sem rede)

```sh
python3 scripts/nucleo_cdc_eca.py verify
python3 -m unittest tests.test_nucleo_cdc_eca -v
```

## Recapturar

```sh
python3 scripts/nucleo_cdc_eca.py fetch /tmp/captura-cdc-eca
python3 scripts/nucleo_cdc_eca.py build /tmp/captura-cdc-eca
```
