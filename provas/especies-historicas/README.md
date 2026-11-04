# Provas — Leis constitucionais, atos institucionais e atos complementares (#90)

Espécies distintas com séries próprias. Dependem dos textos-base históricos da #79 quando houver vínculo; filtros #70 / rastreador #83 ficam com esses lotes.

```bash
python3 scripts/especies_historicas.py reconcile
python3 scripts/especies_historicas.py fetch --limit 30
python3 scripts/especies_historicas.py build
python3 scripts/especies_historicas.py verify
```

## Limites deste lote

Ver `limites.json` (e `matriz-publicacao.json`) para publicados vs retidos (anexo/tabela/título) e pendências de catálogo.

Auditoria integral dos critérios da issue: [`auditoria-criterios-90.md`](auditoria-criterios-90.md).

- 143/143 publicados via Sigen; `normas.leg.br` não indexa a maioria destas espécies.
- `imagens_omitidas: 5` em todas conta chrome do portal Senado, não anexo normativo.
- SHA dos catálogos capturados diverge do SHA citado na issue — divergência preservada.
- Série da espécie no cabeçalho **não** substitui vínculo evidenciado a texto-base (#79) nem inventário dos diplomas alterados.
