# Provas — leis delegadas federais (issue #67)

Lote independente. Reutiliza o conversor de `scripts/nucleo_licitacoes.py` sem alterar aquele gerador.

## Arquivos

| Caminho | Papel |
| --- | --- |
| `senado-LDL.json` | Catálogo oficial de identidades (`tipo=LDL`); SHA da #67 preservado |
| `catalogo-reconciliacao.json` | Identidade, ID Senado, URL, estado de coleta e caminho publicado |
| `fontes.json` | URL, UTC da captura, hashes e cabeçalhos HTTP |
| `fontes/*.htm.xz` | Snapshots oficiais do Planalto (12 leis publicadas neste lote) |
| `reconciliacao-*.json` | Cobertura fonte→Markdown por documento |
| `manifesto.json` | Metadados do lote (sem vigência certificada) |
| `ferramentas.json` | Versões usadas na geração |

## Série

O catálogo do Senado lista **13** leis delegadas. Este lote:

- publica **12** Markdown integrais a partir do Planalto;
- registra a **LDL 7** já presente no acervo (`federal/br-federal-lei-delegada-1962-09-26-7.md`) sem republicá-la.

## Reprodução offline

```bash
python3 scripts/leis_delegadas.py verify
python3 -m unittest tests.test_leis_delegadas -v
```

Regenerar a partir dos snapshots:

```bash
python3 scripts/leis_delegadas.py build
python3 scripts/leis_delegadas.py verify
```

Nova captura (rede):

```bash
python3 scripts/leis_delegadas.py fetch /tmp/ldl-capture
python3 scripts/leis_delegadas.py ingest /tmp/ldl-capture
python3 scripts/leis_delegadas.py build
```

A cobertura exige igualdade textual normalizada entre o HTML da fonte e o Markdown convertido. O catálogo Senado é denominador de identidades; ementa/registro não substituem a íntegra.
