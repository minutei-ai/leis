# Auditoria residual do recorte de limpeza

Base examinada: `4f5dcea855a1170ee4a1ffac202cadf4e08ad8e6`. A lista de
edições adiadas contém 1.423 caminhos: 1.357 federais, 46 estaduais e 20
municipais. São edições protegidas, não contagens de ocorrências de cada
problema. Sua presença na lista não demonstra que todas contenham resíduos.
Não houve colação de fontes nem regeneração de edição nesta auditoria.

| Issue | Evidência e limite | Próximo recorte |
| --- | --- | --- |
| #87 | PR #120 integrou limpeza e adiou edições por hash; o gate exclui as adiadas e não demonstra fidelidade à fonte. Preservação de marcadores, ênfase, tabelas, anexos e riscos precisa ser conferida por edição. | Identificar gerador e captura de um lote homogêneo, comparar origem, saída e prova, corrigir o gerador responsável e só então revalidar hashes. |
| #98 | A extração anterior tem inventário em `imagens.jsonl`; a lista de adiadas não quantifica imagens ainda inline nem permite classificar imagens como decorativas. | Inventariar ocorrências por edição e gerador; conferir cada imagem e preservar conteúdo e proveniência antes de extrair ou omitir. |
| #100 | PR #120 preserva avisos em notas em parte do lote; contagens históricas agregadas não identificam todas as datas ou avisos por edição. | Levantar famílias remanescentes por gerador e migrar informação de proveniência por norma antes de remover linhas. Coletores privados ficam fora deste recorte. |
| #99 | PR #111 registra recoleta dos cinco federais e resolução parcial das duplicatas; PR #138 documenta 17 corpos de MG ainda indisponíveis nas rotas consultadas. Essas descrições não substituem nova colação. | Consultar publicações oficiais ou fac-símiles dos 17 e revisar os grupos de hash e exceções contra as identidades atuais. |
| #70 | PR #126 descreve exportação tipada e testes de filtros; PR #131 corrigiu papéis de fonte e emissor. Cobertura de campos, proveniência e demonstração de busca permanecem dependentes dos critérios da issue. | Auditar o export atual por edição e campo, especialmente datas desconhecidas, identidade e recuperação integral; demonstrar filtros e citação sem declarar vigência. |
| #77 | PR #109 inventariou fac-símiles e descreveu transcrição parcial do formulário do CPP. Hash de imagem não demonstra cobertura textual. | Revisar inventário por peça e transcrever, delimitando ato e página, com colação visual e testes de busca positivos e negativos. |

O resumo histórico `resumo.json` registra passagens da limpeza anterior, não
um censo atual. O campo `skipped_by_reason` das novas execuções conta somente
arquivos efetivamente examinados naquela execução; uma execução parcial não
representa o corpus. Falhas de hash são erros, não edições adiadas válidas.
