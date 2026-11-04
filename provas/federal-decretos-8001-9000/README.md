# Provas — decretos pós-1991, faixa 8001–9000 (issue #81)

Primeiro lote amostral na faixa com maior lacuna aparente entre decretos
numerados pós-1991. Reintegra stubs curtos já presentes e publica três
identidades novas, todos com cobertura fonte→Markdown integral a partir do
Planalto.

Não esgota a faixa nem o cruzamento sistemático com o catálogo Senado DEC.

## Arquivos

| Caminho | Papel |
| --- | --- |
| `fontes.json` / `fontes/*.htm.xz` | Capturas oficiais |
| `reconciliacao-*.json` | Cobertura por documento |
| `manifesto.json` | Metadados do lote |
| `PENDENCIAS-decretos.md` | Publicadas neste lote |
| `ferramentas.json` | Versões |

Mapa por milhar: `provas/federal-lacunas-catalogo/catalogo-81-decretos-milhares.json`.

## Lote

| Número | Estado prévio | Arquivo |
| --- | --- | --- |
| 8100 | stub curto reintegrado | `federal/br-federal-decreto-2013-09-04-8100.md` |
| 8300 | stub curto reintegrado | `federal/br-federal-decreto-2014-08-29-8300.md` |
| 8500 | stub curto reintegrado | `federal/br-federal-decreto-2015-08-12-8500.md` |
| 8600 | stub curto reintegrado | `federal/br-federal-decreto-2015-12-18-8600.md` |
| 8700 | novo | `federal/br-federal-decreto-2016-03-30-8700.md` |
| 8800 | novo | `federal/br-federal-decreto-2016-07-06-8800.md` |
| 8900 | novo | `federal/br-federal-decreto-2016-11-10-8900.md` |

## Limites

- Contagem por milhar usa denominador 1000 por convenção de faixa; números
  inexistentes, vetados ou não usados **não** são lacunas comprovadas.
- Cruzamento com índice oficial Senado/Planalto permanece necessário antes de
  fechar a #81.
- Demais milhares e o restante de 8001–9000 ficam para lotes futuros.

## Reprodução

```bash
python3 scripts/federal_decretos_8001_9000.py verify
python3 -m unittest tests.test_federal_decretos_8001_9000 -v
```
