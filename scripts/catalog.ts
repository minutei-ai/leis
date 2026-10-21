import { Schema } from "effect";

export const Source = Schema.Struct({
  id: Schema.String.pipe(Schema.pattern(/^br-(?:federal|mg)-[a-z0-9-]+$/)),
  titulo: Schema.NonEmptyString,
  data: Schema.String.pipe(Schema.pattern(/^\d{4}-\d{2}-\d{2}$/)),
  fonte: Schema.String.pipe(
    Schema.pattern(
      /^https:\/\/(?:www2\.camara\.leg\.br\/legin\/|normas\.leg\.br\/api\/public\/binario\/|dadosabertos\.almg\.gov\.br\/api\/v2\/legislacao\/mineira\/)/,
    ),
  ),
  marcadorInicial: Schema.optional(Schema.NonEmptyString),
  marcadorFinal: Schema.optional(Schema.NonEmptyString),
});

export const catalog = Schema.decodeUnknownSync(Schema.Array(Source))([
  {
    id: "br-federal-constituicao-1988-10-05",
    titulo: "Constituição da República Federativa do Brasil de 1988",
    data: "1988-10-05",
    fonte:
      "https://www2.camara.leg.br/legin/fed/consti/1988/constituicao-1988-5-outubro-1988-322142-normaatualizada-pl.html",
    marcadorInicial: "Art. 1º",
    marcadorFinal: "Art. 250",
  },
  {
    id: "br-federal-lei-2002-01-10-10406",
    titulo: "Código Civil — Lei nº 10.406/2002",
    data: "2002-01-10",
    fonte:
      "https://www2.camara.leg.br/legin/fed/lei/2002/lei-10406-10-janeiro-2002-432893-normaatualizada-pl.html",
    marcadorInicial: "Art. 1º",
    marcadorFinal: "Art. 2.046",
  },
  {
    id: "br-federal-lei-2015-03-16-13105",
    titulo: "Código de Processo Civil — Lei nº 13.105/2015",
    data: "2015-03-16",
    fonte:
      "https://www2.camara.leg.br/legin/fed/lei/2015/lei-13105-16-marco-2015-780273-normaatualizada-pl.html",
    marcadorInicial: "Art. 1º",
    marcadorFinal: "Art. 1.072",
  },
]);

export const Metadata = Schema.Struct({
  id: Source.fields.id,
  titulo: Schema.String,
  data: Schema.String,
  fonte: Schema.String,
  versao: Schema.Literal(
    "texto atualizado pela Câmara na data de coleta",
    "compilação atual disponibilizada pelo Senado",
    "publicação original disponibilizada pelo Senado",
    "texto atualizado disponibilizado pela ALMG",
    "publicação original disponibilizada pela ALMG",
  ),
  urn: Schema.optional(Schema.NonEmptyString),
  dados: Schema.optional(Schema.NonEmptyString),
  sha256_dados: Schema.optional(Schema.NonEmptyString),
  licenca_fonte: Schema.optional(Schema.NonEmptyString),
  coletado_em: Schema.String,
  sha256_fonte: Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/)),
  sha256_markdown: Schema.String.pipe(Schema.pattern(/^[a-f0-9]{64}$/)),
});
