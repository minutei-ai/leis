# Anexos RCN — fontes alternativas oficiais (#94)

Seis resoluções do Congresso Nacional tinham publicação ANX no Senado com
**HTTP 200 `application/pdf` e 0 bytes**. Isso bloqueia aquela URL; não prova que
a peça seja inacessível em todas as fontes oficiais.

## Recuperação

| Norma | Fonte alternativa | Artefato |
| --- | --- | --- |
| RCN 2/2025 | Câmara legin anexo PDF | `fontes/…2025-06-23-2.anexo.pdf.xz` |
| RCN 1/2025 | Câmara legin anexo PDF | `fontes/…2025-03-14-1.anexo.pdf.xz` |
| RCN 2/2014 | Câmara publicação original HTML (Estatuto AP-CPLP) | `fontes/…2014-01-16-2.anexo.html.xz` |
| RCN 3/2013 | Câmara legin anexo PDF | `fontes/…2013-11-22-3.anexo.pdf.xz` |
| RCN 2/2006 | Senado HTML `…/publicacao/36751146` (PDF `36751141` vazio) | `fontes/…2006-12-26-2.anexo.html.xz` |
| RCN 1/2006 | Câmara legin anexo PDF | `fontes/…2006-12-22-1.anexo.pdf.xz` |

Fac-símiles da 1ª página (quando PDF): `facsimiles/*.p1.png.xz`.
Transcrições: `fontes/*.anexo.txt.xz`.
Inventário: `recuperacao-fontes-alternativas.json`.

## Reprodução

```bash
# Artefatos oficiais já devem estar em /tmp/rcn-stage (captura prévia)
python3 scripts/rcn_anexos_fontes_alternativas.py all
python3 scripts/rcn_anexos_fontes_alternativas.py verify
```

O Markdown publicado em `federal/br-federal-resolucao-congresso-nacional-*.md`
concatena o corpo HTML já coletado com o anexo da fonte alternativa, marcado
por `<!-- anexo-fonte-alternativa:… -->`. Em divergência visual, o fac-símile/PDF
prevalece sobre a transcrição. Vigência não é certificada.
