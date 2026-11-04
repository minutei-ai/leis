# Pendências setoriais — recorte Norte/CO Lei 14.133 (#73/#101)

Não altera `PENDENCIAS.md` agregado nem inventários compartilhados de PR #116.

## Critérios

| Critério | Estado nesta entrega |
| --- | --- |
| Regulamento geral estadual por UF do recorte | Parcial: **AC 11.363**, **MT 1.525** novos; **AM 47.133** e **DF 44.330** reuso; TO 6.606 identificado (PDF colunas); GO suite temática; MS/AP só SRP específico; PA/RO/RR sem geral estadual limpo |
| LO + regulamento geral municipal das capitais | Parcial: **Porto Velho LO + 18.892**; **Boa Vista LO**; demais LO/gerais pendentes ou parciais (Goiânia art.60) |
| DF | Entidade especial; LO-DF e 44.330 reuso; fora do critério municipal #101 |
| Reuso IDs opacos / sem duplicar AM/DF/SP | Atendido |
| Fonte bloqueada ≠ ausência | Atendido (`tentativas.json` + provas TO/Manaus) |

## Coletados nesta entrega

- AC Decreto 11.363/2023 (geral) — LEGIS/AC
- MT Decreto 1.525/2022 (geral) — IOMAT
- MS Decreto 16.122/2023 (específico SRP) — SPDO
- AP Decreto 1.716/2023 (específico SRP) — Transparência/AP PDF→txt
- Porto Velho Decreto 18.892/2023 (geral municipal) — SAPL
- Porto Velho Lei Orgânica 1990 — SAPL texto atual
- Boa Vista Lei Orgânica 1992 — SAPL texto atual

## Identificados não coletados (íntegra limpa)

- TO Decreto 6.606/2023 (geral) — DOE 4862 PDF baixado; colunas intercaladas; HTML 403 (`provas/norte-co-14133/TO/`)
- Manaus Decreto 5.525/2023 (geral municipal) — PDF DOM duas colunas (SHA `8f54f26c…`); misturado com 5.524
- LOMAN (Manaus) — PDF CMM; HTML sem corpo integral
- Belém suite temática (PDF consolidado) — timeout da controladoria

## Capitais ainda sem LO no acervo (recorte)

Rio Branco, Manaus, Macapá, Belém, Palmas, Cuiabá, Campo Grande, Goiânia.

## Fora de escopo

- README / inventários compartilhados PR #116
- Outras UFs (outro agente)
- Constituições estaduais (#86)
