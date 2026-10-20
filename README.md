# Leis brasileiras em Markdown

Acervo público do [Minutei](https://minutei.legal), coletado diretamente de fontes oficiais. Um arquivo Markdown por norma, com origem, versão, data de coleta e hashes SHA-256. O objetivo é ampliar o acesso à legislação brasileira em texto simples, com coleta reproduzível e histórico real das atualizações.

## Acervo inicial

| Norma | Arquivo |
| --- | --- |
| Constituição Federal de 1988 | [Markdown](federal/br-federal-constituicao-1988-10-05.md) |
| Código Civil — Lei nº 10.406/2002 | [Markdown](federal/br-federal-lei-2002-01-10-10406.md) |
| Código de Processo Civil — Lei nº 13.105/2015 | [Markdown](federal/br-federal-lei-2015-03-16-13105.md) |

**Cobertura inicial: 3 normas federais.** Leis estaduais, distritais, municipais e as demais normas federais ainda não estão incluídas. Não há atualização automática habilitada. Cada arquivo representa o texto atualizado servido pela Câmara dos Deputados na data indicada no cabeçalho; a coleta não certifica vigência, eficácia nem completude do portal.

Os textos têm caráter informativo. Consulte a fonte oficial e a publicação no Diário Oficial antes de citar ou aplicar uma norma.

## Proveniência e formato

- `federal/`: texto convertido, com cabeçalho YAML.
- `fontes/`: resposta HTML comprimida e metadados JSON por norma.
- `scripts/catalog.ts`: catálogo explícito, com identificadores estáveis e dispositivos de início/fim esperados.
- `scripts/collect.ts`: coleta sequencial, com timeout, intervalo e validação antes da escrita.

`sha256_fonte` identifica os bytes HTML descomprimidos; `sha256_markdown` identifica o corpo convertido, sem o cabeçalho YAML e o título acrescentados pelo coletor. Datas dos commits representam a coleta ou manutenção, sem atribuir commits a autoridades históricas.

A conversão preserva links absolutos, tabelas, notas e tachados. Não infere revogação nem remove redações históricas. O HTML original fica disponível para conferir perdas de formatação. Validações de tamanho e dispositivos extremos detectam algumas falhas de extração, mas não equivalem a uma revisão jurídica de cada dispositivo.

## Reproduzir

Requer [Bun](https://bun.sh), na versão registrada no CI.

```sh
bun install --frozen-lockfile
bun run check
bun run collect
bun run check
```

Os testes usam os HTMLs oficiais preservados e verificam a reprodução dos Markdown e seus hashes sem acessar a rede. A coleta busca novamente as três fontes. Conteúdo idêntico preserva os arquivos e a data anterior; alterações são registradas em novo commit pelo mantenedor após revisão do diff. Uma falha interrompe o comando com código diferente de zero; normas já gravadas permanecem no disco para inspeção.

## Contribuir

Envie uma issue com a norma e a URL oficial ou um PR com o coletor, a fonte preservada e o Markdown. Novas fontes precisam de validação própria, limites de requisição e evidência de reprodução. Não substitua um texto atualizado por publicação original sob a mesma identidade. Expansão prevista: legislação federal, depois fontes estaduais e municipais, com contagens verificáveis por fonte.

O projeto é independente. A referência encontrada durante a pesquisa foi [ctresb/leis](https://github.com/ctresb/leis); não usamos seu acervo nem seus scripts.

## Licença

O código deste projeto usa a [licença MIT](LICENSE). Os textos oficiais permanecem sujeitos ao regime próprio dos atos oficiais; a licença do código não atribui ao Minutei autoria sobre as normas. Metadados e organização produzidos pelo projeto também são disponibilizados sob MIT.
