# Auditoria dos grupos SHA-1 idênticos (issue #99) — atualização 2026-11-04

Fonte estadual consultada: ALMG (fichas de ementa + API `dadosabertos` com campos `ementa`/`nomes`/`resumo`/`texto`), sem inferir ausência por HTTP. Evidências API em `mg-recoleta/*.json.xz`.

## Resumo

| Tipo | Qtd | Significado |
| --- | --- | --- |
| `alias_catalogo` | 13 | Mesma norma (mesma epígrafe) sob duas chaves de catálogo (BA/GO/MS/RJ/município 5218805) |
| `mesmo_texto_fonte_com_ressalva` | 1 | 35816/35817 — ementa e nomes ALMG idênticos; bytes iguais; ressalva sem microfilme |
| Desmembrados (não mais SHA-1 idêntico) | 19 pares→arquivos | Corpo correto no caminho certo; caminho órfão com nota `corpo_digital_indisponivel` |

Os 5 decretos federais da issue (#99) permanecem recolecionados e **não** entram nesta lista.

## Matriz dos 12 grupos `pendencia_identidade` (resolução parcial)

Critério: ementa ALMG diverge; Markdown era o mesmo corpo. Ação: manter corpo no caminho cuja ficha/nomes batem; substituir o outro por nota documental (sem inventar dispositivo a partir da ementa). HTML ALMG do número órfão continua a servir o corpo errado — evidência preservada.

| Par | Corpo mantido em | Órfão / recuperado | Identidade do órfão (ficha) | Estado residual |
| --- | --- | --- | --- | --- |
| 803/804 (1937) | `…-804` Manhumirim | **`…-803` recuperado** (JMG 09/04/1937 p.2 — 4.ª escola Joaima/Jequitinhonha) | Escola distrital Jequitinhonha | íntegra publicada; crops `jmg/crop-803-*.png` |
| 2159/2160 (1945) | `…-2159` Sete Lagoas | `…-2160` nota (`nao_publicado_integra`) | 2º grupo escolar Pouso Alegre | JMG sem edição digital 1945; IOF/microfilme |
| 3996/3997 (1953) | `…-3996` José Donato | `…-3997` nota | Magalhães Drumont | JMG sem edição digital 1953 |
| 5082/5085 (1956) | `…-5082` transfere Álvaro | `…-5085` nota | Extingue função isolada (DJ) | JMG sem edição digital 1956 |
| 5120/5121 (1956) | `…-5121` transfere Antônio | `…-5120` nota | Extingue/transforma Vigilante Policial | JMG sem edição digital 1956 |
| 12612/12704 (1970) | `…-12612` José Teubner | `…-12704` nota | Lotação Regina da Costa Val | JMG sem edição digital 1970 |
| 17645/17720 | `…-17645` Darowish | `…-17720` nota | Lotação Carlos Aniceto Pimenta (motorista) | JMG sem edição digital 1976 |
| 18653/18693 (1977) | `…-18653` Olivia Pinto | `…-18693` nota | Padre Lourenço → Márcio Nicolato | JMG sem edição digital 1977 |
| 22346/1982 × lei/2016 | `…lei-2016-…-22346` Limeira | `…decreto-1982-…-22346` nota | Crédito FJP CR$ 63.417.500,00 | JMG sem edição digital 1982 |
| 36566/36574 (1994) | `…-36566` crédito DER 26/12 | `…-36574` nota | Ficha 27/12; HTML ALMG ainda traz 26/12 | JMG sem edição digital 1994 |
| 40951/40955 (2000) | `…-40951` FEAM R$200.000,00 | **`…-40955` recuperado** (JMG 22/03/2000 p.1 — FIA R$327.713,81) | FIA R$327.713,81 | íntegra publicada; crops `jmg/crop-40955-*.png` |
| 10454/10523 (1991) | `…-10454` Bias Fortes | `…-10523` nota | Permuta Sapucaí-Mirim | JMG sem edição digital 1991 |

Inventário máquina: `mg-orfaos-inventario.json` (2 recuperados / 17 pendentes). Notas trazem `Status_publicacao: nao_publicado_integra`, `edicao_integral: false`, `excluir_denominador_integra: true` — presença/hash **não** reclassifica como íntegra. Fonte ALMG incorreta dos recuperados em `mg-recoleta/fonte-incorreta-historica/`.

## Matriz dos 9 grupos `mesmo_texto_fonte_com_ressalva` (reauditoria)

A ementa genérica ALMG era idêntica; a reauditoria usou `nomes`/`resumo` da ficha.

| Par | Achado | Ação |
| --- | --- | --- |
| 7720/7721 | Nomes Angelo × Etelvina; HTML = Angelo | Mantido 7720; nota em 7721 |
| 9983/9985 | Nomes Hely × Marly; HTML = Hely | Mantido 9983; nota em 9985 |
| 35816/35817 | Nomes **iguais** (N. Sra. das Graças) | **Preservado** como ressalva (único remanescente na lista SHA-1) |
| 36127/36128 | Nomes Vila Kennedy × Afonso Pena; HTML = Afonso Pena | Mantido 36128; nota em 36127 |
| 37343/37344 | Nomes Vereador José × Juscelino; HTML = Juscelino | Mantido 37344; nota em 37343 |
| 37349/37351 | API entrega corpos **distintos** (Zacarias × Valentina); corpus tinha Valentina nos dois | **Recoleta** 37349 (Zacarias Roque) da API; 37351 Valentina mantida |
| 37352/37353 | Nomes Monsenhor Mendes × Marechal Hermes; HTML = Hermes | Mantido 37353; nota em 37352 |
| 37365/37367 | Nomes Cristiano Machado × Maria de Lourdes; HTML = Cristiano | Mantido 37365; nota em 37367 |
| 37373/37374 | Nomes Afrânio × Alfredo Valadão; HTML = Alfredo | Mantido 37374; nota em 37373 |

Não se finge resolução plena onde o corpo integral do número órfão permanece indisponível na fonte digital.

## Aliases de catálogo (justificados)

BA (4), GO (1), MS (2), RJ (5), município Rio Verde/5218805 (1): epígrafe do corpo idêntica nos dois arquivos; chaves de catálogo distintas.

Detalhe máquina: `duplicatas-excecoes.json`.
