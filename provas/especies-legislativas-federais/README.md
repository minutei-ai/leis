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
| `urls-legin-camara-rcd-resolvidas.json` | URLs `publicacaooriginal` resolvidas para citações do Regimento |
| `bloqueio-anexos-rcn-pdf-vazio.json` | Evidência: ANX Senado HTTP 200 com PDF de 0 bytes |
| `matriz-criterios-issues.md` | Matriz por critério de aceite (issues abertas) |
| `fontes/camara-bd-regimento-30ed-2026.*` | Snapshots oficiais (PDF/EPUB/texto) do Regimento 30ª ed. |
| `coleta.json` / `coletas/` | Coleta retomável de HTML (checkpoint por item) |
| `fontes.json` / `manifesto.json` / `cobertura-conversao.json` | Provas do Markdown publicado neste lote |

## Reprodução

```bash
python3 scripts/especies_legislativas_federais.py capture
python3 scripts/especies_legislativas_federais.py reconcile
python3 scripts/especies_legislativas_federais.py discover-camara-rcd
python3 scripts/especies_legislativas_federais.py collect --tipos RCN --all-pending
python3 scripts/especies_legislativas_federais.py collect --tipos DLG,RSF,RCD --dlg-limit 250 --rsf-limit 250 --rcd-limit 250
python3 scripts/especies_legislativas_federais.py collect-camara-rcd
python3 scripts/especies_legislativas_federais.py build
python3 scripts/especies_legislativas_federais.py verify
python3 -m unittest tests.test_especies_legislativas_federais -v
```

A coleta é retomável: `--no-resume` descarta o checkpoint; sem `--all-pending` respeita os limites `--*-limit` / alvos iniciais.

## Fontes de texto

- **DLG / parte de RCN:** HTML em `normas.leg.br` (`/api/public/binario/.../texto`), a partir da URN LexML.
- **RSF / RCD Senado / fallback:** HTML da publicação na página do Senado (`/norma/{id}/publicacao/{pubId}`).
- **RCD pós-1991 (Câmara):** HTML `www2.camara.leg.br/legin/fed/rescad/.../publicacaooriginal-...-pl.html` via `collect-camara-rcd`.
- HTML de erro/login/WAF e fragmentos sem corpo normativo são rejeitados antes da publicação.
- Anexos Senado (`ANX` com `temTexto=S`) bloqueiam publicação como íntegra (`anexos-pendentes`).

## Limites deste lote

- Catálogo Senado reconciliado; Markdown avança por coleta retomável (não limitado a 5 amostras).
- **RCN:** 82/88 publicados; 6 `anexos-pendentes` com PDF ANX oficial vazio (0 bytes) — ver `bloqueio-anexos-rcn-pdf-vazio.json`.
- **RCD Senado** até 1991-09-25. Descoberta Câmara: 63 citações no Regimento; 13 íntegras legin publicadas; índices anuais `/legin/.../YYYY/` → 403.
- LexML WAF; PRC na API de proposições ≠ resolução promulgada.
- Presença no catálogo ou no repositório não certifica vigência.
- README agregado / contagens globais ficam com a coordenação.
