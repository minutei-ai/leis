# Leis brasileiras em Markdown

Acervo público do [Minutei](https://minutei.legal), coletado diretamente de fontes oficiais. Um arquivo Markdown por norma, com origem, versão, data de coleta e hashes SHA-256. O objetivo é ampliar o acesso à legislação brasileira em texto simples, com coleta reproduzível e histórico real das atualizações.

As quantidades publicadas, os catálogos consultados e o que falta coletar estão em **[COBERTURA.md](COBERTURA.md)**. O acervo está em formação e ainda não contém todas as leis brasileiras. Não há atualização automática habilitada.

## Consultar

- [Constituição Federal de 1988](federal/br-federal-constituicao-1988-10-05.md)
- [Código Civil — Lei nº 10.406/2002](federal/br-federal-lei-2002-01-10-10406.md)
- [Código de Processo Civil — Lei nº 13.105/2015](federal/br-federal-lei-2015-03-16-13105.md)
- [Demais normas federais](federal/)
- [Normas de Minas Gerais](estaduais/MG/)

O cabeçalho de cada arquivo informa a versão: texto atualizado da Câmara, compilação atual disponibilizada pelo Senado ou publicação original. O coletor do Senado prefere a compilação atual em HTML; se ela não existir nos metadados, usa a publicação original em HTML. Retificações isoladas não substituem uma norma inteira. O projeto não infere vigência nem eficácia a partir da versão disponível.

Os textos têm caráter informativo. Consulte a fonte e a publicação no Diário Oficial antes de citar ou aplicar uma norma.

## Fontes e proveniência

A descoberta federal usa a [API de Dados Abertos do Senado](https://legis.senado.leg.br/dadosabertos/api-docs/swagger-ui/index.html), particionada por tipo e ano. Os metadados do [Portal das Normas Jurídicas Brasileiras](https://normas.leg.br/) fornecem os arquivos de texto e suas versões. O acesso aos arquivos segue o caminho público usado pelo próprio portal. Os três documentos iniciais vieram diretamente da [Legislação Informatizada da Câmara](https://www2.camara.leg.br/atividade-legislativa/legislacao).

- `federal/`: texto convertido, com cabeçalho YAML.
- `estaduais/MG/`: normas mineiras convertidas de fontes da ALMG.
- `fontes/`: HTML comprimido, metadados JSON e respostas JSON originais do Senado e da ALMG.
- `catalogos/almg/`: inventários anuais e CSVs oficiais comprimidos de Minas Gerais.
- `catalogos/senado/<tipo>/<ano>.json`: inventário identificado e pendências de identidade.
- `catalogos/senado/<tipo>/<ano>.fonte.json.gz`: resposta original do catálogo oficial, inclusive quando vazio.
- `falhas/`: erros individuais; uma coleta posterior bem-sucedida remove o erro correspondente.
- `scripts/`: descoberta, coleta, conversão, auditoria e relatório.

`sha256_fonte` identifica os bytes HTML descomprimidos; `sha256_dados` identifica a resposta JSON de metadados descomprimida, quando presente; `sha256_markdown` identifica o corpo convertido, sem o cabeçalho YAML e o título acrescentados pelo coletor. A URN identifica a norma por autoridade, tipo, data e número, incluindo complemento quando existir. Datas dos commits representam coleta ou manutenção.

A conversão preserva links absolutos, tabelas, notas e tachados, inclusive tachados declarados em estilos inline. Não remove redações históricas. Imagens e anexos vinculados continuam como referências; o coletor não baixa esses recursos nem executa OCR. O HTML original permite conferir a transformação. Tamanho mínimo e presença do artigo inicial detectam algumas falhas; os três documentos iniciais também exigem dispositivos finais específicos. Isso não equivale a uma revisão jurídica integral.

A coleta mineira usa o CSV anual e os documentos da [API de Dados Abertos da ALMG](https://dadosabertos.almg.gov.br/). Prefere o link de texto atualizado quando o catálogo o fornece e, caso contrário, usa a publicação original. O JSON recebido é preservado e a auditoria verifica a identidade do documento e a extração do HTML.

## Skills jurídicas

Os guias em `skills/` orientam agentes e pessoas a pesquisar e analisar normas com fontes verificáveis:

- [Pesquisa legislativa](skills/pesquisa-legislativa/SKILL.md): localizar normas, conferir proveniência e registrar lacunas.
- [Vigência e aplicação](skills/vigencia-e-aplicacao/SKILL.md): identificar a redação pertinente ao tempo e ao território dos fatos.
- [Interpretação jurídica](skills/interpretacao-juridica/SKILL.md): examinar requisitos, exceções, teses e aplicação aos fatos.

Para usar manualmente, abra o guia e siga o procedimento com os arquivos do acervo. Para um agente, mantenha o clone acessível e peça que leia o `SKILL.md` escolhido antes da análise. Em ferramentas compatíveis com esse formato, copie a pasta inteira da skill para o diretório de skills da ferramenta; a descoberta e a ativação dependem dela. Os guias não instalam ferramentas, não atualizam o acervo e não conferem acesso à internet.

Exemplo de pedido ao agente:

```text
Leia skills/pesquisa-legislativa/SKILL.md e skills/interpretacao-juridica/SKILL.md.
Pesquise no Código Civil a diferença entre personalidade e capacidade.
Confira a fonte oficial, cite os dispositivos e separe texto legal de interpretação.
Declare se não conseguir confirmar a redação atual.
```

As skills são roteiros de pesquisa, sujeitos a revisão; não certificam vigência nem substituem a análise profissional de um caso.

## Reproduzir e ampliar

Requer [Bun](https://bun.sh), na versão registrada no CI.

```sh
bun install --frozen-lockfile
bun run check

# atualizar os três documentos iniciais da Câmara
bun run collect

# descobrir leis ordinárias federais por ano
bun run discover --from 1822 --to 2026 --type LEI

# coletar os textos dos catálogos locais, retomando arquivos íntegros
bun run collect:senado

# descobrir o catálogo anual mineiro sem baixar os textos
bun run collect:almg --from 2026 --to 2026 --discover-only

# coletar um lote mineiro, retomando arquivos íntegros
bun run collect:almg --from 2026 --to 2026 --limit 100

# auditar todos os arquivos publicados e regenerar as contagens
bun run audit
bun run coverage
```

Famílias aceitas: `LEI`, `LCP`, `LDL`, `DEL`, `EMC`. Execute a descoberta para cada família desejada. Intervalos ausentes do relatório ainda não foram consultados. A API do Senado não fornece, nessa operação, paginação ou um total independente para certificar a completude da resposta.

A descoberta reutiliza catálogos locais. Para atualizar um ano já consultado, use `bun run discover --from 2026 --to 2026 --type LEI --refresh`. A coleta pode ser limitada com `bun run collect:senado --limit 100`; use `--refresh` para consultar novamente textos já íntegros. Respostas idênticas preservam os arquivos e a data anterior. Mudanças devem ser revisadas no diff antes de novo commit.

As requisições são sequenciais, com intervalo e timeout. Uma falha na descoberta interrompe o comando; catálogos já concluídos são preservados para retomada. Na coleta dos textos, uma falha é registrada por norma e as demais continuam; o processo termina com código diferente de zero se houver falhas. Arquivos incompletos ou com hashes divergentes são recolhidos na próxima execução. Uma interrupção pode deixar arquivos parciais: confira a auditoria antes de publicar.

Os testes usam fontes reais preservadas, sem acesso à rede, e cobrem identidade, versões, rejeição de páginas inválidas e conversão. `bun run audit` verifica os hashes e reproduz a conversão de todas as normas disponíveis no checkout. O CI executa ambos. O relatório mede o material presente, sem equiparar reprodução e hash a completude nacional.

## Contribuir

Envie uma issue com a norma e a URL oficial ou um PR com o coletor, a fonte preservada e o Markdown. Novas fontes precisam de validação própria, limites de requisição e evidência de reprodução. Não substitua um texto atualizado por publicação original sob a mesma identidade. A expansão inclui as demais famílias federais e fontes estaduais, distritais e municipais, com contagens verificáveis por fonte.

Agradecemos ao pessoal da **Supersonic Labs** pela inspiração para tornar a legislação brasileira mais acessível em Markdown. A referência encontrada durante a pesquisa foi [ctresb/leis](https://github.com/ctresb/leis). Este projeto é uma iniciativa independente do Minutei, com coleta própria de fontes oficiais; não usamos o acervo nem os scripts daquele repositório.

## Licenças e créditos

Código, documentação e skills produzidos pelo Minutei usam a [licença MIT](LICENSE). Os textos oficiais permanecem sujeitos ao regime próprio dos atos oficiais; a licença do código não atribui ao Minutei autoria sobre as normas.

Os dados e arquivos obtidos do Portal das Normas Jurídicas Brasileiras são atribuídos ao Senado Federal, à Câmara dos Deputados e ao Congresso Nacional, conforme os metadados de cada fonte. Preserve também a licença indicada em `licenca_fonte` — nas respostas já coletadas, [Creative Commons Atribuição 4.0](https://creativecommons.org/licenses/by/4.0/) — e a origem dos textos ao redistribuir. A conversão para Markdown e o cabeçalho de proveniência são alterações feitas pelo Minutei. Os metadados originais permanecem preservados em `fontes/`.
