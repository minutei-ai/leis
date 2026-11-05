# Matriz de entrega — issues #99 / #102

## #99 — 12 pares pendencia_identidade

| Par | Critério | Resultado | Prova |
| --- | --- | --- | --- |
| 803/804 | Corpos distintos; 804=Manhumirim; 803=Joaima/Jequitinhonha | **803 recuperado** (JMG 1937-04-09 p.2); 804 ok | `mg-recoleta/jmg/crop-803-*.png` |
| 2159/2160 | 2159=Sete Lagoas; ficha 2160=Pouso Alegre; captura 2160 repete Sete Lagoas | 2160 continua nota: captura oficial ALMG atual confirma texto vizinho, sem recuperar corpo correto | `mg-recoleta/almg-texto-original-capturas.json`; `api-DEC-2160-1945.json.xz` |
| 3996/3997 | 3996=Donato; ficha 3997=Magalhães Drumont; captura 3997 repete Donato | 3997 continua nota: corpo ALMG não corresponde à ficha | `mg-recoleta/almg-texto-original-capturas.json`; `api-DEC-3997-1953.json.xz` |
| 5082/5085 | 5082=transfere; ficha 5085=extingue função isolada | 5085 continua nota: corpo ALMG transfere Operador e não corresponde à ficha | `mg-recoleta/almg-texto-original-capturas.json`; `api-DEC-5085-1956.json.xz` |
| 5120/5121 | ficha 5120 trata Vigilante Policial; captura 5120 transfere Auxiliar de Escritório | 5120 continua nota: corpo ALMG não corresponde à ficha | `mg-recoleta/almg-texto-original-capturas.json`; `api-DEC-5120-1956.json.xz` |
| 12612/12704 | ficha 12704=Regina da Costa Val; captura 12704=José Teubner | 12704 continua nota: corpo ALMG não corresponde à ficha | `mg-recoleta/almg-texto-original-capturas.json`; `api-DEC-12704-1970.json.xz` |
| 17645/17720 | ficha 17720=Carlos Aniceto Pimenta; captura 17720=José Paulo Darowish | 17720 continua nota: corpo ALMG não corresponde à ficha | `mg-recoleta/almg-texto-original-capturas.json`; `api-DEC-17720-1976.json.xz` |
| 18653/18693 | ficha 18693=Padre Lourenço → Márcio Nicolato; captura=Olivia Pinto | 18693 continua nota: corpo ALMG não corresponde à ficha | `mg-recoleta/almg-texto-original-capturas.json`; `api-DEC-18693-1977.json.xz` |
| 22346/1982×2016 | ficha Decreto 22346=crédito FJP; captura corpo é Lei 22346/2016, Limeira | 22346 continua nota: corpo ALMG não corresponde à ficha | `mg-recoleta/almg-texto-original-capturas.json`; `api-DEC-22346-1982.json.xz` |
| 36566/36574 | corpo de 36574 fecha em 26/12; ficha data 36574 em 27/12; texto extraído coincide com 36566 após decodificar entidades e colapsar espaços | 36574 continua nota: evidência atual não permite atribuir o corpo com segurança | `mg-recoleta/almg-texto-original-capturas.json`; `api-DEC-36574-1994.json.xz` |
| 40951/40955 | 40951=FEAM; 40955=FIA | **40955 recuperado** (JMG 2000-03-22 p.1); 40951 ok | `mg-recoleta/jmg/crop-40955-*.png` |
| 10454/10523 | 10454=Bias Fortes; ficha 10523=permuta Sapucaí-Mirim; captura 10523 repete Bias Fortes | 10523 continua nota: corpo ALMG não corresponde à ficha | `mg-recoleta/almg-texto-original-capturas.json`; `api-LEI-10523-1991.json.xz` |

Inventário máquina: `mg-orfaos-inventario.json` (2 recuperados / 17 pendentes com `edicao_integral=false` e `excluir_denominador_integra=true`).

JMG digitalização verificada em 2026-11-04: anos **1937** e **2000** com edições no calendário da API; anos dos demais órfãos **sem** edição digital. Em 2026-11-05 foram capturadas e confrontadas as 17 páginas ALMG “Texto Original”; os corpos não correspondem com segurança às fichas (em 36574, fecho interno e duplicação com 36566 contradizem a data). Veja `mg-recoleta/auditoria-almg-orfaos-2026-11-05.md`. A Série 12 do inventário público APM lista documentos legislativos apenas até 1934; isso não prova ausência em outros acervos. Ausência de texto na API ALMG **não** foi tomada como indisponibilidade universal.

## #99 — 9 mesmo_texto_fonte_com_ressalva

| Par | Achado | Resultado |
| --- | --- | --- |
| 7720/7721 | Nomes Angelo×Etelvina; captura oficial 7721 repete Angelo | 7720 mantido; 7721 nota; ver captura e comparação em `mg-recoleta/almg-texto-original-capturas.json` |
| 9983/9985 | Nomes Hely×Marly; captura oficial 9985 repete Hely | 9983 mantido; 9985 nota; ver captura e comparação em `mg-recoleta/almg-texto-original-capturas.json` |
| 35816/35817 | Nomes idênticos | Preservado com ressalva (único SHA-1 remanescente) |
| 36127/36128 | Vila Kennedy×Afonso Pena; captura oficial 36127 repete Afonso Pena | 36128 mantido; 36127 nota; ver captura e comparação em `mg-recoleta/almg-texto-original-capturas.json` |
| 37343/37344 | Vereador José×Juscelino; captura oficial 37343 repete Juscelino | 37344 mantido; 37343 nota; ver captura e comparação em `mg-recoleta/almg-texto-original-capturas.json` |
| 37349/37351 | API corpos distintos | **37349 recoleta Zacarias**; 37351 Valentina |
| 37352/37353 | Mendes×Hermes; captura oficial 37352 repete Hermes | 37353 mantido; 37352 nota; ver captura e comparação em `mg-recoleta/almg-texto-original-capturas.json` |
| 37365/37367 | Cristiano×Maria; captura oficial 37367 repete Cristiano | 37365 mantido; 37367 nota; ver captura e comparação em `mg-recoleta/almg-texto-original-capturas.json` |
| 37373/37374 | Afrânio×Alfredo; captura oficial 37373 repete Alfredo | 37374 mantido; 37373 nota; ver captura e comparação em `mg-recoleta/almg-texto-original-capturas.json` |

## #102 — lote ampliado delimitado

| Ato | Catálogo | Publicação Senado | Corpus | Critério |
| --- | --- | --- | --- | --- |
| 45171 | 45.171 (467738) | literal `41.171` (pub 15805509) | preserva `41.171` | Erro literal da fonte |
| 45353 | 45.353 (467918) | literal `453.353` (pub 15700630) | preserva `453.353` | Erro literal da fonte |
| 46934 | 46.934 (469503) | literal `56.934` (pub 15804419) | preserva `56.934` | Erro literal da fonte |
| 4.014-A | mantido | `1.014-A` documentado | Câmara `4.014-A` | Já colacionado |

## #103 / #104

Preservados: corpos 12.985/12.988; anexos DL 1873/2111; célula **NS-4 a 6** e crops Câmara+Planalto.
