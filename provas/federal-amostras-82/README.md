# Provas — amostras issue #82 (leis 1822–1965 e 2010–2026)

Lote amostral das identidades citadas na issue #82, fora do recorte #71
(1966–2009). Publica íntegras recuperadas no Planalto com cobertura
fonte→Markdown. Não esgota as 2.589 (1822–1965) + 172 (2010–2026) identidades
do denominador Senado.

## Arquivos

| Caminho | Papel |
| --- | --- |
| `fontes.json` / `fontes/*.htm.xz` | Capturas oficiais |
| `reconciliacao-*.json` | Cobertura por documento |
| `manifesto.json` | Metadados do lote |
| `catalogo-pendencias.json` | Estado das 12 amostras da issue |
| `PENDENCIAS-amostras.md` | Publicadas / pendentes (404 Planalto) |
| `ferramentas.json` | Versões |

Catálogo amplo: `provas/federal-lacunas-catalogo/catalogo-82-resumo.json`.

## Série amostral

- **9** Markdown integrais neste lote (4923; 13898; 14059; 14087; 14642; 14823; 14847; 14950; 15103).
- **3** pendentes com Planalto HTTP 404 nesta captura (4920, 4921, 4926) — ausência de URL
  não prova inexistência; busca continua em normas.leg.br / Câmara.

## Reprodução

```bash
python3 scripts/federal_amostras_82.py verify
python3 -m unittest tests.test_federal_amostras_82 -v
```

Regenerar a partir dos snapshots:

```bash
python3 scripts/federal_amostras_82.py build
python3 scripts/federal_amostras_82.py verify
```
