# Provas — LGPD (Lei 13.709/2018)

Catálogo temático separado do núcleo de licitações.

## Conteúdo

- `fontes.json` — URL, captura, hashes e cabeçalhos HTTP
- `fontes/*.html.xz` / `*.htm.xz` — snapshots oficiais (Câmara e Planalto)
- `cobertura-conversao-camara.json` — equivalência blocos convertidos ↔ corpo Markdown
- `reconciliacao-br-federal-lei-2018-08-14-13709-consolidada.json` — Câmara × Planalto artigo a artigo
- `historica-vs-consolidada-13709.json` — edição histórica preservada × consolidada
- `dispositivos-alvo-mp1317-lei15352.json` — arts. 5º VIII/XIX, Cap. IX, Seção I, 55-A, 55-C
- `validacao-lei-15352.json` — reuso da modificadora já publicada (anexos só no snapshot)

## Reprodução offline

```bash
python3 scripts/lgpd.py verify
python3 -m unittest tests.test_lgpd -v
```

`verify` reconverte o snapshot Câmara (`lzma` → `convert_html` → Markdown) e compara o corpo normativo publicado; confere hashes dos snapshots e o `sha256_corpo_preservado` da edição histórica.

## Limites

- O acervo não certifica vigência.
- A edição histórica não tem fonte/captura registradas (`desconhecido`).
- O Markdown já publicado da Lei 15.352/2026 não traz as tabelas dos Anexos I–III; os bytes oficiais estão no snapshot Planalto.
