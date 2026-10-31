"""Verifica arquivos publicados; não certifica integralidade jurídica dos atos."""
import hashlib
import json
from pathlib import Path
import re

root = Path(__file__).resolve().parent.parent
entries = [json.loads(line) for line in (root / 'assets/dou/MANIFESTO.jsonl').read_text().splitlines()]
seen = set()
for entry in entries:
    relative = entry['arquivo']
    assert relative not in seen, f'Imagem duplicada: {relative}'
    seen.add(relative)
    path = (root / relative).resolve()
    assert path.is_relative_to(root / 'assets/dou'), relative
    assert path.is_file(), f'Imagem ausente: {relative}'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256_imagem'], relative
    assert entry['pdf_pagina'] > 0, relative
    assert re.fullmatch(r'[0-9a-f]{64}', entry['pdf_sha256']), relative

references = 0
for md in (root / 'federal').glob('*.md'):
    text = md.read_text()
    if '<!-- fac-simile-oficial:inicio -->' not in text:
        continue
    assert text.count('<!-- fac-simile-oficial:inicio -->') == 1, md.name
    assert text.count('<!-- fac-simile-oficial:fim -->') == 1, md.name
    for relative in re.findall(r'!\[[^\]]*\]\(([^)]+)\)', text):
        path = (md.parent / relative).resolve()
        assert path.is_relative_to(root), (md.name, relative)
        assert path.is_file(), (md.name, relative)
        if path.is_relative_to(root / 'assets/dou'):
            assert str(path.relative_to(root)) in seen, (md.name, relative)
            references += 1
print(f'{len(entries)} imagens com hashes íntegros; {references} referências verificadas. A completude documental exige revisão separada.')
