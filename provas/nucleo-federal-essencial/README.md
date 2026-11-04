# Núcleo federal essencial — matriz unificada (issue #62)

Matriz de cobertura por **área** e **identidade normativa** das seis leis priorizadas na issue #62. Contagem de arquivos no `federal/` **não** é o único controle.

Os textos integrais já foram publicados em lotes separados; esta pasta só unifica backlog, diagnóstico de coleta e o gate de identidade.

| Área | Norma | `norma_id` | Estado | Lote / PR |
| --- | --- | --- | --- | --- |
| Consumidor | Lei 8.078/1990 (CDC) | `br-federal-lei-1990-09-11-8078` | publicado | [cdc-eca](../nucleo-cdc-eca/) / [#78](https://github.com/minutei-ai/leis/pull/78) |
| Infância e adolescência | Lei 8.069/1990 (ECA) | `br-federal-lei-1990-07-13-8069` | publicado | [cdc-eca](../nucleo-cdc-eca/) / [#78](https://github.com/minutei-ai/leis/pull/78) |
| Tributário | Lei 5.172/1966 (CTN) | `br-federal-lei-1966-10-25-5172` | publicado | [ctn-sus](../nucleo-federal-ctn-sus/) / [#76](https://github.com/minutei-ai/leis/pull/76) |
| Saúde | Lei 8.080/1990 (SUS) | `br-federal-lei-1990-09-19-8080` | publicado | [ctn-sus](../nucleo-federal-ctn-sus/) / [#76](https://github.com/minutei-ai/leis/pull/76) |
| Previdenciário | Lei 8.213/1991 | `br-federal-lei-1991-07-24-8213` | publicado | [beneficios-mdp](../nucleo-federal-beneficios-mdp/) / [#80](https://github.com/minutei-ai/leis/pull/80) |
| Violência doméstica | Lei 11.340/2006 | `br-federal-lei-2006-08-07-11340` | publicado | [beneficios-mdp](../nucleo-federal-beneficios-mdp/) / [#80](https://github.com/minutei-ai/leis/pull/80) |

## Artefatos

- Manifesto máquina: [`metadados/matriz-nucleo-federal-essencial.json`](../../metadados/matriz-nucleo-federal-essencial.json)
- Contrato: [`metadados/CONTRATO-matriz-nucleo-federal-essencial.md`](../../metadados/CONTRATO-matriz-nucleo-federal-essencial.md)
- Diagnósticos por lote (não substituídos por esta matriz):
  - [`../nucleo-cdc-eca/diagnostico-coleta-cdc-eca.md`](../nucleo-cdc-eca/diagnostico-coleta-cdc-eca.md)
  - [`../nucleo-federal-ctn-sus/diagnostico-coleta.md`](../nucleo-federal-ctn-sus/diagnostico-coleta.md)
  - [`../nucleo-federal-beneficios-mdp/diagnostico-coleta.md`](../nucleo-federal-beneficios-mdp/diagnostico-coleta.md)

## Separação de `PENDENCIAS.md`

`PENDENCIAS.md` lista **peças acompanhantes** de atos já publicados (plantas, anexos gráficos, etc.). As seis identidades desta matriz eram **ausência do diploma integral**, não peça faltante de arquivo existente. Permanecem fora de `PENDENCIAS.md`.

## Diagnóstico unificado da lacuna original

Padrão observado nos três lotes: **identificada e ainda não coletada**.

1. Cada identidade já constava do catálogo anual do Senado (`LEI/AAAA.json`) com `senadoId` e sem pendência no JSON do catálogo.
2. No coletor privado não havia Markdown, captura em `fontes/` nem `falhas/<id>.json` canônico.
3. O pipeline padrão Senado → `normas.leg.br` não havia concluído essas filas; a recuperação pública usou Planalto (e Câmara para a Lei 11.340).
4. Menções em leis modificadoras ou contagem de arquivos no `federal/` **não** substituem o texto integral.

## Limites

- Escopo **parcial**: só estas seis identidades.
- `vigencia_certificada` permanece `false`; situação e efeitos seguem o que cada lote e fonte registram.
- Não inventaria atos infralegais (#72/#75), decretos legislativos (#65) nem resoluções do Senado (#66).
- Não altera README agregado nem o manifesto do núcleo de licitações.
