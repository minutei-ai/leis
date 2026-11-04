# Provas — Lei 8.213/1991 (benefícios) e Lei 11.340/2006 (Maria da Penha)

Lote independente do núcleo de licitações. Reutiliza o conversor de `scripts/nucleo_licitacoes.py` sem alterar aquele gerador.

## Arquivos

| Caminho | Papel |
| --- | --- |
| `fontes.json` | URL, UTC da captura, hashes, cabeçalhos HTTP, aviso DOU (quando houver) |
| `fontes/*.htm.xz` / `*.html.xz` | Snapshots oficiais (Planalto e Câmara) |
| `reconciliacao-br-federal-lei-1991-07-24-8213.json` | Cobertura fonte→Markdown e métricas da Lei 8.213 |
| `reconciliacao-br-federal-lei-2006-08-07-11340.json` | Idem para a Lei 11.340 |
| `manifesto.json` | Metadados do lote (sem vigência certificada) |
| `diagnostico-coleta.md` | Por que essas duas identidades faltavam |
| `ferramentas.json` | Versões usadas na geração |

Markdown publicado:

- `federal/br-federal-lei-1991-07-24-8213.md`
- `federal/br-federal-lei-2006-08-07-11340.md`

## Reprodução offline

```bash
python3 scripts/nucleo_federal_beneficios_mdp.py verify
python3 -m unittest tests.test_nucleo_federal_beneficios_mdp -v
```

Para regenerar a partir dos snapshots preservados:

```bash
python3 scripts/nucleo_federal_beneficios_mdp.py build
python3 scripts/nucleo_federal_beneficios_mdp.py verify
```

Nova captura (rede):

```bash
python3 scripts/nucleo_federal_beneficios_mdp.py fetch /tmp/beneficios-mdp-capture
python3 scripts/nucleo_federal_beneficios_mdp.py ingest /tmp/beneficios-mdp-capture
python3 scripts/nucleo_federal_beneficios_mdp.py build
```

A cobertura exige igualdade textual normalizada entre o HTML da fonte e o Markdown convertido (`strip_fold(source_text_chars_from_html) == strip_fold(md_text_all(body))`), não apenas coincidência de hashes ou de frases isoladas.
