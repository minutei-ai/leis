# Pendências setoriais — Sul/Sudeste 14.133 (#73/#101)

Namespace `sul-sudeste-14133`. Não altera o `PENDENCIAS.md` agregado nem os índices compartilhados `regulamentacao-14133-ufs` / `capitais-lei-organica-14133`.

## Critérios

| Critério | Estado neste lote |
| --- | --- |
| Inventário ≠ coleta; HTTP≠ausência | comprovado (bloqueios por fonte/ente) |
| Reuso IDs opacos sem duplicar | comprovado (PR 10.086; suite MG/SP; BH temáticos; SP LO+62.100) |
| Parcial/temático ≠ geral | comprovado (SC 30; POA 21.978; BH 18.289; ES 5307/5352/5353) |
| LO integral com notas/ADCT | Vitória (HTML fold); Curitiba (PDF 101 págs); SP reuso |
| PDF: todas páginas + bbox | Curitiba 101; POA 12; ES Word tagged (pypdf); ES DOE 5354/5545 bbox pendente |

## Coleta retomável

- **ES 5.354-R / 5.545-R**: fontes SEGER/DOE capturadas em `provas/sul-sudeste-14133/ES/fontes/`; conversão com bounding boxes + recorte do ato (páginas multi-ato) pendente. Suite 5307/5352/5353 publicada.
- **RJ suite** (48.816/48.820/48.843/48.778): IOERJ/ALERJ; Câmara RJ TLS falhou.
- **RS suite** (57.034/57.036/56.937): ALRS legis degradado; `legislacao.camarapoa.rs.gov.br` 403.
- **SC** SRP 509/2024, obras 358/2023 (ALESC; busca sem URL estável de ato).
- **BH LO**: página CMBH `/lei-organica` é shell de busca; API SIL `cmbhsilint.cmbh.mg.gov.br` DNS NXDOMAIN.
- **Curitiba Dec. 380/2023+**: `curitiba.pr.gov.br` Akamai Denied; leismunicipais WAF.
- **Florianópolis LO/reg**: CMF mínimo; SAPL DNS fail; PMF aponta leismunicipais (WAF).
- **POA LO** e decreto geral: SAPL DNS; legislação CMPA 403; WAF leismunicipais.
- **Rio LO/reg**: TLS Câmara RJ.
- **Vitória decreto geral municipal**: LO ok; reggeral ainda não recuperado.

## Fora de escopo

- Norte/Centro-Oeste/Nordeste (outros agentes).
- Constituições estaduais (#86).
- README / índices compartilhados / PENDENCIAS agregados.
