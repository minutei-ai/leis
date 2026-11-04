# Provas — prioridade #71 (leis 5.000–11.999)

Lote parcial das normas essenciais citadas na issue #71, recuperadas do Planalto
com cobertura fonte→Markdown integral. Não esgota as ~7.061 identidades do
catálogo Senado no período 1966–2009.

## Arquivos

| Caminho | Papel |
| --- | --- |
| `fontes.json` / `fontes/*.htm.xz` | Capturas oficiais |
| `reconciliacao-*.json` | Cobertura por documento |
| `manifesto.json` | Metadados do lote |
| `PENDENCIAS-prioridade.md` | Prioridades restantes / já cobertas |
| `ferramentas.json` | Versões |

## Reprodução

```bash
python3 scripts/federal_prioridade_5000_11999.py verify
```

Normas já publicadas por outros lotes (#62 / núcleos) não são republicadas aqui;
aparecem em `PENDENCIAS-prioridade.md`.
