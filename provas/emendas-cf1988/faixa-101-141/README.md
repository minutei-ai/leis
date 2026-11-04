# Provas — Emendas CF/1988 faixa 101–141

Geradas por [`scripts/emendas_cf1988_faixa_101_141.py`](../../../scripts/emendas_cf1988_faixa_101_141.py). Não editar à mão.

| Arquivo | Função |
| --- | --- |
| `fontes/` | Snapshots oficiais do Planalto (HTML em `.xz`). |
| `fontes.json` | URL, data UTC, status HTTP, hashes e cabeçalhos de cada captura. |
| `matriz.json` | Matriz por número/data/fonte/situação deste lote. |
| `manifesto.json` | Metadados dos 33 documentos publicados. |
| `reconciliacao-*.json` | Cobertura HTML→Markdown e reconversão por emenda. |
| `ferramentas.json` | Versões usadas na geração. |

## Verificar (sem rede)

```sh
python3 scripts/emendas_cf1988_faixa_101_141.py verify
python3 -m unittest tests.test_emendas_cf1988_faixa_101_141 -v
```

## Recapturar

```sh
python3 scripts/emendas_cf1988_faixa_101_141.py fetch /tmp/captura-emendas-cf1988-faixa-101-141
python3 scripts/emendas_cf1988_faixa_101_141.py ingest /tmp/captura-emendas-cf1988-faixa-101-141
python3 scripts/emendas_cf1988_faixa_101_141.py build
```
