# Provas — Emendas CF/1988, faixa 001–050

Lote independente do issue [#63](https://github.com/minutei-ai/leis/issues/63): recupera apenas os números **ausentes** da série da Constituição de 1988 entre 1 e 50.

## Escopo deste lote

`5, 6, 7, 8, 11, 13, 15, 16, 19, 20, 27, 29, 32, 33, 34, 35, 37, 41, 42, 43, 45`

- Série: emendas à CF/1988 (`emecon`, ano ≥ 1988).
- Fora do escopo: emendas constitucionais de revisão (`emecrv`) e emendas a constituições históricas (mesmo número, data pré-1988).
- A matriz geral e o README público do repositório ficam com a coordenação; esta pasta documenta só o lote.

## Conteúdo

| Artefato | Função |
| --- | --- |
| `catalogo-lote.json` | Número, data de promulgação, ementa, URLs Câmara/Planalto |
| `matriz-lote.json` | Situação da coleta/publicação, notas e riscos por número |
| `fontes.json` | Capturas UTC, hashes, cabeçalhos HTTP |
| `fontes/*.xz` | Snapshots oficiais (portal, quadro Planalto, cada EC) |
| `cobertura-conversao.json` | Blocos → Markdown, reconversão idêntica, SHA-256 |
| `reconciliacao-camara-planalto.json` | Conferência artigo a artigo quando o Planalto foi capturado |

## Reprodução

```bash
python3 scripts/emendas_cf1988_faixa_001_050.py check-absent
python3 scripts/emendas_cf1988_faixa_001_050.py convert
python3 scripts/emendas_cf1988_faixa_001_050.py verify
python3 -m unittest tests.test_emendas_cf1988_faixa_001_050 -v
```

Fonte principal do Markdown publicado: **Câmara — publicação original**. Planalto entra como conferência. Acesso falho a uma fonte não é tratado como inexistência da norma.

## Limites

- O acervo **não certifica vigência**.
- O texto publicado é o ato autônomo da emenda (artigos próprios, transição, efeitos, fecho), não só a redação que a Constituição consolidada absorveu.
- Divergências tipográficas/editoriais Câmara × Planalto podem existir sem invalidar a publicação baseada na Câmara.
