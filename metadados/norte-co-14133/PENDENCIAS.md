# Pendências setoriais — recorte Norte/CO Lei 14.133 (#73/#101)

Não altera `PENDENCIAS.md` agregado nem inventários compartilhados de PR #116.

## Critérios

| Critério | Estado nesta entrega |
| --- | --- |
| Regulamento geral estadual por UF do recorte | Parcial: **AC 11.363**, **MT 1.525**, **TO 6.606** novos; **AM 47.133** e **DF 44.330** reuso; GO suite temática; MS/AP só SRP específico; PA/RO/RR sem geral estadual limpo |
| LO + regulamento geral municipal das capitais | Parcial: **Porto Velho LO + 18.892**; **Boa Vista LO**; **Manaus LO + 5.525**; demais LO/gerais pendentes ou parciais (Goiânia art.60) |
| DF | Entidade especial; LO-DF e 44.330 reuso; fora do critério municipal #101 |
| Reuso IDs opacos / sem duplicar AM/DF/SP | Atendido |
| Fonte bloqueada ≠ ausência | Atendido (`tentativas.json` + provas) |

## Coletados nesta entrega (acumulado)

- AC Decreto 11.363/2023 (geral) — LEGIS/AC
- MT Decreto 1.525/2022 (geral) — IOMAT (auditoria: chrome de portal no fecho)
- MS Decreto 16.122/2023 (específico SRP) — SPDO
- AP Decreto 1.716/2023 (específico SRP) — Transparência/AP PDF→txt
- Porto Velho Decreto 18.892/2023 (geral municipal) — SAPL
- Porto Velho Lei Orgânica 1990 — SAPL texto atual
- Boa Vista Lei Orgânica 1992 — SAPL texto atual
- **TO Decreto 6.606/2023 (geral)** — DOE site 4862 / impresso 6299; colunas por coordenadas + colação visual
- **Manaus Decreto 5.525/2023 (geral municipal)** — DOM ed.5555; colunas; separado de 5.524
- **LOMAN (Manaus)** — PDF CMM atualizado Emenda 120/2024; layout monopágina

## Identificados / bloqueados (íntegra limpa ainda pendente)

- Belém suite temática (PDF consolidado) — timeout da controladoria
- Gerais estaduais PA/RO/RR
- LOs Rio Branco, Macapá, Belém, Palmas, Cuiabá, Campo Grande, Goiânia (fontes DNS/404/403 nesta sessão — ≠ ausência)

## Auditoria das sete publicações anteriores

| Norma | Identidade | Âmbito | Nota |
| --- | --- | --- | --- |
| AC 11.363 | ok (Art.1 regulamenta 14.133 estadual) | geral | íntegra longa (361 arts) |
| MT 1.525 | ok | geral | chrome IOMAT/Ionews no fecho |
| MS 16.122 | ok | **específico SRP** (≠ geral) | 36 arts |
| AP 1.716 | ok | **específico SRP** arts 82–86 (≠ geral) | 19 arts |
| PV 18.892 | ok | geral municipal | 148 arts |
| PV LO | ok (PREÂMBULO) | LO | 283 arts |
| BV LO | ok (PREÂMBULO) | LO | 357 arts |

## Fora de escopo

- README / inventários compartilhados PR #116
- Outras UFs (outro agente)
- Constituições estaduais (#86)
