import { expect, test } from "bun:test";
import { mkdir, mkdtemp, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Schema } from "effect";
import { Metadata } from "./catalog";

test("publicação original não sobrescreve a versão atualizada já registrada", async () => {
  const directory = await mkdtemp(join(tmpdir(), "leis-version-"));
  const id = "br-federal-lei-2002-01-10-10406";
  const prior = await Bun.file(`fontes/${id}.json`).text();
  const metadata = Schema.decodeUnknownSync(Schema.parseJson(Metadata))(prior);
  await mkdir(join(directory, "fontes"));
  await Bun.write(join(directory, `fontes/${id}.json`), prior);
  await symlink(join(import.meta.dir, "../node_modules"), join(directory, "node_modules"), "dir");
  const program = `import { Effect } from "effect";
import { saveDocument } from ${JSON.stringify(join(import.meta.dir, "document.ts"))};
const result = await Effect.runPromise(saveDocument(${JSON.stringify({ ...metadata, versao: "publicação original disponibilizada pelo Senado" })}, new Uint8Array([1]), "Original", undefined).pipe(Effect.either));
console.log(result._tag);
`;
  const child = Bun.spawn(["bun", "-e", program], { cwd: directory, stdout: "pipe", stderr: "pipe" });
  expect(await child.exited).toBe(0);
  expect((await new Response(child.stdout).text()).trim()).toBe("Left");
  expect(await Bun.file(join(directory, `fontes/${id}.json`)).text()).toBe(prior);
  expect(await Bun.file(join(directory, `fontes/${id}.html.gz`)).exists()).toBe(false);
  await rm(directory, { recursive: true });
});
