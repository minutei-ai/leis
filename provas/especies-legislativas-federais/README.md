# Provas — Espécies legislativas federais (DLG, RSF, RCD, RCN)

Lote dos issues [#65](https://github.com/minutei-ai/leis/issues/65), [#66](https://github.com/minutei-ai/leis/issues/66), [#89](https://github.com/minutei-ai/leis/issues/89) e [#94](https://github.com/minutei-ai/leis/issues/94).

## Escopo

| Código | Espécie | Órgão emissor | Issue |
| --- | --- | --- | --- |
| DLG | Decreto Legislativo | Congresso Nacional | #65 |
| RSF | Resolução do Senado Federal | Senado Federal | #66 |
| RCD | Resolução da Câmara dos Deputados | Câmara dos Deputados | #89 |
| RCN | Resolução do Congresso Nacional | Congresso Nacional | #94 |

Espécies distintas: número/ano sem órgão não identifica a norma. Não confundir com decreto do Executivo nem com decreto-lei (`DEL`).

## Artefatos

| Arquivo | Função |
| --- | --- |
| `catalogos.json` + `fontes/senado-lista-*.json.xz` | Capturas oficiais da API do Senado, com hashes |
| `reconciliacao-*.json` | Identidade, ID, URL, URN, estado de coleta e caminho publicado |
| `resumo-reconciliacao.json` | Totais por espécie |
| `limites-catalogos.json` | Limites do catálogo RCD (Senado até 1991) e fontes complementares |
| `descoberta-camara-rcd-pos-1991.json` | Catálogo complementar de RCD pós-1991 por citações do Regimento BD Câmara |
| `fontes/camara-bd-regimento-30ed-2026.*` | Snapshots oficiais (PDF/EPUB/texto) do Regimento 30ª ed. |
| `coleta.json` / `coletas/` | Coleta retomável de HTML (checkpoint por item) |
| `fontes.json` / `manifesto.json` / `cobertura-conversao.json` | Provas do Markdown publicado neste lote |

## Reprodução

```bash
python3 scripts/especies_legislativas_federais.py capture
python3 scripts/especies_legislativas_federais.py reconcile
python3 scripts/especies_legislativas_federais.py discover-camara-rcd
python3 scripts/especies_legislativas_federais.py collect --tipos RCN --all-pending
python3 scripts/especies_legislativas_federais.py collect --tipos DLG,RSF,RCD --all-pending
python3 scripts/especies_legislativas_federais.py build
python3 scripts/especies_legislativas_federais.py verify
python3 -m unittest tests.test_especies_legislativas_federais -v
```

A coleta é retomável: `--no-resume` descarta o checkpoint; sem `--all-pending` respeita os limites `--*-limit` / alvos iniciais.

## Fontes de texto

- **DLG / parte de RCN:** HTML em `normas.leg.br` (`/api/public/binario/.../texto`), a partir da URN LexML.
- **RSF / RCD / fallback:** HTML da publicação na página do Senado (`/norma/{id}/publicacao/{pubId}`), usando o ID linkado na página quando o JSON de detalhe aponta só para PDF vazio.
- HTML de erro/login/WAF e fragmentos sem corpo normativo são rejeitados antes da publicação.
- Anexos Senado (`ANX` com `temTexto=S`) bloqueiam publicação como íntegra (`anexos-pendentes`).

## Limites deste lote

- O catálogo Senado foi reconciliado por identidade; a íntegra Markdown avança por coleta retomável (prioridade RCN).
- A lista do Senado para **RCD** observa o intervalo até 1991. A descoberta complementar no Regimento oficial da Câmara (30ª ed., até Resolução 16/2025) registra citações número/ano pós-1991; citação no consolidado **não** substitui a íntegra do ato.
- LexML e listagens `/legin/fed/rescad/` ficaram inacessíveis (WAF/403) nesta captura — limites declarados em `descoberta-camara-rcd-pos-1991.json`.
- RCN com anexos essenciais pendentes permanecem `anexos-pendentes` (não publicados como íntegra).
- Presença no catálogo ou no repositório não certifica vigência.
- README agregado / contagens globais ficam com a coordenação.
