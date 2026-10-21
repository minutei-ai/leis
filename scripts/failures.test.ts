import { expect, test } from "bun:test";
import { oldestFailures } from "./failures";

test("retentativas limitadas atendem primeiro as falhas antigas e preservam a entrada", () => {
  const failures = [
    { id: "nova", coletado_em: "2026-10-21T12:00:00.000Z", erro: "HTTP 503" },
    { id: "antiga", coletado_em: "2026-10-20T12:00:00.000Z", erro: "Sem texto" },
  ];
  expect(oldestFailures(failures, 1)).toEqual(["antiga"]);
  expect(failures[0]?.id).toBe("nova");
  const retried = failures.map((failure) => {
    if (failure.id === "antiga") return { ...failure, coletado_em: "2026-10-22T12:00:00.000Z" };
    return failure;
  });
  expect(oldestFailures(retried, 1)).toEqual(["nova"]);
});
