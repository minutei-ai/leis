"""Extração técnica de candidatos; não certifica completude documental."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.parse


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


manifest = json.loads(Path('scripts/dou-review-pages.json').read_text())
output = Path('dou-review-output')
output.mkdir(exist_ok=True)
results = []
try:
    for name, document in manifest['documents'].items():
        url = document['url']
        assert urllib.parse.urlparse(url).hostname == 'biblioteca.in.gov.br'
        assert Path(name).name == name
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder) / name
            # curl uses the runner's native TLS stack. Keep certificate verification
            # enabled; a source access failure must remain a failed check.
            transfer = subprocess.run([
                'curl', '--fail', '--show-error', '--silent', '--location',
                '--proto', '=https', '--proto-redir', '=https',
                '--connect-timeout', '30', '--max-time', '240',
                '--max-filesize', str(256 * 1024 * 1024),
                '--user-agent', 'minutei-ai-leis-source-review/1.0',
                '--write-out', '%{http_code} %{content_type} %{url_effective}',
                '--output', str(pdf), url,
            ], capture_output=True, text=True)
            if transfer.returncode:
                results.append({'pdf': name, 'state': 'falha-de-download',
                                'exit_code': transfer.returncode,
                                'error': transfer.stderr[-2000:]})
                print(f'{name}: download falhou ({transfer.returncode})', flush=True)
                time.sleep(2)
                continue
            actual_pdf_sha = sha(pdf)
            if actual_pdf_sha != document['sha256']:
                with pdf.open('rb') as stream:
                    prefix = stream.read(64)
                results.append({'pdf': name, 'state': 'hash-pdf-divergente',
                                'expected': document['sha256'], 'actual': actual_pdf_sha,
                                'bytes': pdf.stat().st_size, 'response': transfer.stdout,
                                'prefix_hex': prefix.hex()})
                print(f'{name}: hash PDF divergente; resposta {transfer.stdout}', flush=True)
                time.sleep(2)
                continue
            for page, expected in document['pages'].items():
                page_number = int(page)
                assert page_number > 0
                prefix = Path(folder) / f'page-{page}'
                subprocess.run(['pdfimages', '-f', page, '-l', page, '-png', str(pdf), str(prefix)], check=True)
                images = sorted(Path(folder).glob(f'page-{page}-*.png'))
                if len(images) != 1:
                    raise ValueError(f'Esperada uma imagem por página: {name}, {page}, {len(images)}')
                extracted = images[0]
                actual = sha(extracted)
                expected_hash = expected.get('expected_png_sha256')
                state = 'idêntico-em-bytes' if actual == expected_hash else ('comparação-pixel-pendente' if expected_hash else 'nova-página-para-leitura')
                target = output / f'{Path(name).stem}-p{page_number:02}.png'
                extracted.replace(target)
                results.append({'pdf': name, 'page': page_number, 'png': target.name, 'sha256': actual, 'expected': expected_hash, 'state': state})
            time.sleep(2)
finally:
    (output / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')

if any(row['state'] in {'falha-de-download', 'hash-pdf-divergente'} for row in results):
    raise SystemExit('Há fontes não obtidas ou divergentes; ver results.json no artefato.')
