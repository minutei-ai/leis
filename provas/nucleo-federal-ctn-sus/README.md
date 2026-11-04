# Provas — CTN (Lei 5.172/1966) e Lei 8.080/1990 (SUS)

Lote independente do núcleo de licitações. Reutiliza o conversor de `scripts/nucleo_licitacoes.py` sem alterar aquele gerador.

## Arquivos

| Caminho | Papel |
| --- | --- |
| `fontes.json` | URL, UTC da captura, hashes, cabeçalhos HTTP, aviso DOU |
| `fontes/*.htm.xz` | Snapshots oficiais Planalto |
| `reconciliacao-br-federal-lei-1966-10-25-5172.json` | Cobertura fonte→Markdown e métricas de conversão do CTN |
| `reconciliacao-br-federal-lei-1990-09-19-8080.json` | Idem para a Lei 8.080/1990 |
| `manifesto.json` | Metadados do lote (sem vigência certificada) |
| `diagnostico-coleta.md` | Por que essas duas identidades faltavam |
| `ferramentas.json` | Versões usadas na geração |

Markdown publicado:

- `federal/br-federal-lei-1966-10-25-5172.md`
- `federal/br-federal-lei-1990-09-19-8080.md`

## Reprodução offline

```bash
python3 scripts/nucleo_federal_ctn_sus.py verify
python3 -m unittest tests.test_nucleo_federal_ctn_sus -v
```

Para regenerar a partir dos snapshots preservados:

```bash
python3 scripts/nucleo_federal_ctn_sus.py build
python3 scripts/nucleo_federal_ctn_sus.py verify
```

Nova captura (rede):

```bash
python3 scripts/nucleo_federal_ctn_sus.py fetch /tmp/ctn-sus-capture
python3 scripts/nucleo_federal_ctn_sus.py ingest /tmp/ctn-sus-capture
python3 scripts/nucleo_federal_ctn_sus.py build
```

A cobertura exige igualdade textual normalizada entre o HTML da fonte e o Markdown convertido (`strip_fold(source_text_chars_from_html) == strip_fold(md_text_all(body))`), não apenas coincidência de hashes ou de frases isoladas.
