"""Regressões da recuperação PR do Decreto 10.086/2022 (licitações locais).

Lê somente arquivos do repositório; não acessa a rede.
A conferência de texto bruto da região normativa usa BeautifulSoup +
nucleo_licitacoes.strip_fold/md_text_all (sem o conversor Paraná privado).
Execute: python3 -m unittest tests.test_licitacoes_locais_pr -v
"""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import nucleo_licitacoes as nl  # noqa: E402

CATALOG = ROOT / "metadados" / "licitacoes-locais" / "PR.json"
DOC = ROOT / "estaduais" / "PR" / "br-pr-ato-259084.md"
PROOF = ROOT / "provas" / "licitacoes-locais" / "PR"
FONTES = PROOF / "fontes.json"
ORIG_MD = PROOF / "br-pr-ato-259084-original.md"
COMPILADO_XZ = PROOF / "fontes" / "legislacao-pr-259084-compilado.htm.xz"
ORIGINAL_XZ = PROOF / "fontes" / "legislacao-pr-259084-original.htm.xz"
PORTAL_DISCLAIMER = "Este texto não substitui o publicado no Diário Oficial do Estado"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def content_sha_html(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    cleaned = re.sub(r";jsessionid=[^\"'?\s]+", "", text)
    return sha256_bytes(cleaned.encode("utf-8"))


def normative_region_text(raw_html: bytes) -> str:
    """Texto bruto da região normativa da impressão oficial Paraná.

    Extrai `#conteudo_corpo > form[name=listarAtosAnoForm]`, remove controles do
    portal e o aviso final que não entra no Markdown publicado.
    """
    soup = BeautifulSoup(raw_html.decode("utf-8", errors="replace"), "lxml")
    form = soup.select_one("#conteudo_corpo > form[name=listarAtosAnoForm]")
    if form is None:
        raise AssertionError("região normativa paranaense ausente no snapshot")
    for tag in form.find_all(["script", "style", "input", "button", "select", "textarea"]):
        tag.decompose()
    text = form.get_text(" ")
    idx = text.rfind(PORTAL_DISCLAIMER)
    if idx >= 0:
        text = text[:idx]
    return text


def markdown_fold_text(markdown: str) -> str:
    """Fold do Markdown alinhado ao texto HTML (ênfase removida antes do ordinal)."""
    text = nl.md_text_all(markdown)
    # `**Art.148** O` deixaria o "O" colado ao dígito só depois do strip_fold;
    # remover ênfase antes evita assimetria com o get_text do HTML.
    text = re.sub(r"[*_]+", "", text)
    return nl.strip_fold(text)


class TestLicitacoesLocaisPR(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.fontes = json.loads(FONTES.read_text(encoding="utf-8"))
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.orig = ORIG_MD.read_text(encoding="utf-8")
        cls.entry = cls.catalog["documentos"][0]
        cls.compilado_raw = lzma.open(COMPILADO_XZ).read()
        cls.original_raw = lzma.open(ORIGINAL_XZ).read()

    def test_catalogo_minimo_parcial_pr(self) -> None:
        self.assertEqual(self.catalog["uf"], "PR")
        self.assertEqual(self.catalog["cobertura"], "parcial")
        self.assertIn("documentos", self.catalog)
        self.assertIn("reutilizados", self.catalog)
        self.assertIn("pendencias", self.catalog)
        self.assertEqual(len(self.catalog["documentos"]), 1)
        self.assertTrue(self.catalog["pendencias"])

    def test_documento_identidade_fonte_259084(self) -> None:
        e = self.entry
        self.assertEqual(e["norma_id"], "br-pr-ato-259084")
        self.assertEqual(e["arquivo"], "estaduais/PR/br-pr-ato-259084.md")
        self.assertEqual(e["uf"], "PR")
        self.assertIsNone(e["ibge_municipio"])
        self.assertEqual(e["esfera"], "estadual")
        self.assertEqual(e["orgao"]["cod_ato_fonte"], "259084")
        self.assertEqual(e["identidade"]["numero"], "10086")
        self.assertEqual(e["identidade"]["data"], "2022-01-17")
        self.assertTrue(DOC.is_file())

    def test_ambito_estadual_nao_municipal_generico(self) -> None:
        ambito = self.entry["ambito"]
        self.assertEqual(ambito["abrangencia"], "estadual")
        self.assertEqual(ambito["ente"], "Estado do Paraná")
        literal = ambito["poder_administracao"]["literal"]
        self.assertIn("Administração Pública estadual", literal)
        self.assertIn("direta, autárquica e fundacional", literal)
        self.assertIn("Estado do Paraná", literal)
        adesao = ambito["adesao"]["literal"]
        self.assertIn("Poderes Legislativo e Judiciário", adesao)
        self.assertIn("aderir", adesao.lower())
        for item in ambito["nao_abrangido_por_inferencia"]:
            self.assertIsInstance(item, str)
        self.assertIn("municípios do Paraná", ambito["nao_abrangido_por_inferencia"])
        self.assertIn("endereço do fornecedor", ambito["nao_abrangido_por_inferencia"])
        self.assertNotIn("municipal", self.entry["esfera"])

    def test_markdown_preserva_alteracoes_e_revogacoes(self) -> None:
        self.assertIn("Decreto 10086 - 17 de Janeiro de 2022", self.doc)
        self.assertIn("Lei Federal nº 14.133", self.doc)
        self.assertIn("Administração Pública estadual", self.doc)
        self.assertIn("Redação dada", self.doc)
        self.assertIn("Revogado", self.doc)
        self.assertIn("Incluído", self.doc)
        self.assertIn("~~", self.doc)
        self.assertIn("**Art. 1º**", self.doc)
        self.assertIn("**Art. 734.**", self.doc)
        self.assertIn("1.º de abril de 2023", self.doc)
        self.assertIn("Carlos Massa Ratinho Junior", self.doc)

    def test_corpo_historico_nao_sobrescrito(self) -> None:
        self.assertTrue(ORIGINAL_XZ.is_file())
        self.assertTrue(ORIG_MD.is_file())
        self.assertNotEqual(sha256_file(DOC), sha256_file(ORIG_MD))
        self.assertGreater(len(self.doc), len(self.orig))
        self.assertNotIn("Redação dada", self.orig)
        self.assertNotIn("~~", self.orig)
        self.assertEqual(
            self.entry["edicao"]["corpo_historico_original"]["sha256_markdown_prova"],
            sha256_file(ORIG_MD),
        )
        self.assertEqual(self.entry["edicao"]["tipo"], "compilada")

    def test_hashes_fontes_e_markdown(self) -> None:
        compilado_key = "legislacao-pr-259084-compilado"
        raw = self.compilado_raw
        meta = self.fontes[compilado_key]
        self.assertEqual(meta["sha256_fonte"], sha256_bytes(raw))
        self.assertEqual(meta["sha256_conteudo"], content_sha_html(raw))
        self.assertEqual(meta["sha256_snapshot_armazenado"], sha256_file(COMPILADO_XZ))
        self.assertEqual(self.entry["hashes"]["sha256_markdown"], sha256_file(DOC))
        self.assertEqual(self.entry["captura"]["sha256_markdown"], sha256_file(DOC))
        for key in (
            "legislacao-pr-259084-original",
            "legislacao-pr-259084-alterado",
            "legislacao-pr-259084-exibirAto",
        ):
            snap = ROOT / self.fontes[key]["snapshot"]
            self.assertTrue(snap.is_file(), key)
            self.assertEqual(
                self.fontes[key]["sha256_snapshot_armazenado"],
                sha256_file(snap),
                key,
            )

    def test_texto_bruto_compilado_igual_markdown_publicado(self) -> None:
        """Conferência independente de TODO o texto bruto da região normativa.

        Não declara integralidade só por sentinelas: o fold do HTML oficial
        compilado tem de coincidir com o do Markdown publicado.
        """
        html_fold = nl.strip_fold(normative_region_text(self.compilado_raw))
        md_fold = markdown_fold_text(self.doc)
        self.assertEqual(html_fold, md_fold)
        self.assertGreater(len(html_fold), 500_000)
        self.assertTrue(self.entry["edicao"]["edicao_integral_conferida_contra_snapshot"])

    def test_texto_bruto_original_igual_markdown_prova(self) -> None:
        """Prova do corpo histórico: HTML original ≡ Markdown de prova (fold)."""
        html_fold = nl.strip_fold(normative_region_text(self.original_raw))
        md_fold = markdown_fold_text(self.orig)
        self.assertEqual(html_fold, md_fold)
        self.assertGreater(len(html_fold), 400_000)
        self.assertNotEqual(html_fold, markdown_fold_text(self.doc))

    def test_reconversao_nucleo_preserva_texto_bruto_da_regiao(self) -> None:
        """Reconversão via nucleo_licitacoes (disponível no CI), além do fold.

        O conversor Paraná privado (coletores/convert.ts) formata títulos/artigos
        de outro modo e não roda no CI; aqui a reconversão do núcleo confirma que
        o texto jurídico da região normativa reaparece integralmente no Markdown
        publicado após strip_fold, sem depender do turndown externo.
        """
        soup = BeautifulSoup(
            self.compilado_raw.decode("utf-8", errors="replace"), "lxml"
        )
        form = soup.select_one("#conteudo_corpo > form[name=listarAtosAnoForm]")
        self.assertIsNotNone(form)
        for tag in form.find_all(["script", "style", "input", "button", "select", "textarea"]):
            tag.decompose()
        # Remove o disclaimer do portal antes da reconversão.
        for node in form.find_all(string=re.compile(re.escape(PORTAL_DISCLAIMER))):
            node.extract()
        wrapped = (
            "<html><body>" + str(form) + "</body></html>"
        ).encode("utf-8")
        url = self.fontes["legislacao-pr-259084-compilado"]["url"]
        converted = nl.convert_html(wrapped, "utf-8", url)
        recon_md = "\n\n".join(converted.blocks) + "\n"
        # A reconversão do núcleo não replica `###`/`**Art.**` do perfil PR;
        # confere o texto bruto completo, não a formatação byte-a-byte.
        self.assertEqual(
            nl.strip_fold(re.sub(r"[*_]+", "", nl.md_text_all(recon_md))),
            markdown_fold_text(self.doc),
        )
        self.assertIn("Carlos Massa Ratinho Junior", recon_md)
        self.assertIn("14.133", recon_md)
        self.assertNotIn(PORTAL_DISCLAIMER, recon_md)

    def test_sem_duplicata_por_cod_ato(self) -> None:
        matches = list((ROOT / "estaduais" / "PR").glob("*259084*"))
        self.assertEqual([p.name for p in matches], ["br-pr-ato-259084.md"])
        for path in (ROOT / "estaduais" / "PR").glob("br-pr-ato-*.md"):
            if path.name == "br-pr-ato-259084.md":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("codAto=259084", text)
            self.assertNotIn("Decreto 10086 - 17 de Janeiro de 2022", text)

    def test_relacoes_federais_com_evidencia_e_desconhecidos(self) -> None:
        rel = self.entry["relacoes_federais"]
        self.assertEqual(rel["estado"], "parcial")
        geral = rel["regulamento_geral"]
        self.assertEqual(geral["norma_federal"], "Lei 14.133/2021")
        self.assertEqual(geral["evidencia"], "literal")
        self.assertIn("14.133", geral["trecho_art1"])
        self.assertIn("Administração Pública estadual", geral["trecho_art1"])
        citados = rel["dispositivos_citados_literalmente"]
        self.assertGreaterEqual(len(citados), 20)
        for item in citados:
            self.assertEqual(item["evidencia"], "literal_no_corpo")
            self.assertIn("14.133", item["trecho"])
            self.assertTrue(item["dispositivo_federal"].startswith("art."))
            # O trecho do catálogo é janela do Markdown publicado.
            needle = re.sub(r"\s+", " ", item["trecho"]).strip()
            haystack = re.sub(r"\s+", " ", self.doc)
            self.assertIn(needle[:60], haystack, item["dispositivo_federal"])
        self.assertTrue(rel["desconhecido"])
        self.assertTrue(any("mapa completo" in d for d in rel["desconhecido"]))

    def test_limites_e_pendencias_explicitas(self) -> None:
        limites = self.entry["limites"]
        self.assertIs(limites["vigencia_certificada"], False)
        self.assertEqual(limites["cobertura_catalogo"], "parcial")
        self.assertIn("nenhum", limites["anexos_em_arquivo_proprio_na_fonte"])
        self.assertTrue(limites["alertas_preservados"])
        ids = {p["id"] for p in self.catalog["pendencias"]}
        self.assertIn("pr-mapa-14133-completo", ids)
        self.assertIn("pr-doe-facsimile-ato", ids)

    def test_negativo_nao_declara_integralidade_nacional_nem_vigencia(self) -> None:
        blob = json.dumps(self.catalog, ensure_ascii=False).lower()
        self.assertNotIn("cobertura\": \"integral\"", json.dumps(self.catalog))
        self.assertEqual(self.catalog["cobertura"], "parcial")
        self.assertIs(self.entry["limites"]["vigencia_certificada"], False)
        self.assertNotIn("vigencia_certificada\": true", blob)
        # Não misturar âmbito com endereço de fornecedor
        self.assertNotIn("fornecedor", self.entry["ambito"]["poder_administracao"]["literal"].lower())

    def test_snapshot_compilado_contem_identidade_e_art1(self) -> None:
        html = self.compilado_raw.decode("utf-8", errors="replace")
        self.assertIn('name="codAto"', html)
        self.assertIn('value="259084"', html)
        self.assertIn("Decreto 10086 - 17 de Janeiro de 2022", html)
        # A impressão oficial usa entidades HTML no corpo.
        self.assertIn("Administra&ccedil;&atilde;o P&uacute;blica estadual", html)
        self.assertIn("14.133", html)
        self.assertIn("<strike", html.lower())
        # Assinaturas e notas de alteração estão na região normativa (não só no MD).
        region = normative_region_text(self.compilado_raw)
        self.assertIn("Carlos Massa Ratinho Junior", region)
        self.assertIn("João Carlos Ortega", region)
        self.assertIn("Letícia Ferreira da Silva", region)
        self.assertIn("Redação dada", region)
        self.assertIn("Revogado", region)
        self.assertIn("Incluído", region)


if __name__ == "__main__":
    unittest.main()
