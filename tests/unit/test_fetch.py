"""Pinned retrieval over local HTTP, with small synthetic compressed archives."""
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import lzma
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import threading
from time import perf_counter, sleep

import numpy as np
import pytest

import certoutage as co
from certoutage import _banks, _fetch as fetch, _prepare as prep
from certoutage import _generate_gain as gen, _chernoff as ch


COMBINATIONS = [(1, 'exact'), (1, 'eq3'), (1, 'chernoff'),
                (2, 'exact'), (2, 'eq3'), (3, 'exact'), (3, 'eq3')]


def forbidden(*args, **kwargs):
    raise AssertionError('Unexpected network, generation or write')


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv('CERTOUTAGE_CACHE_DIR', str(tmp_path / 'cache'))
    monkeypatch.delenv('CERTOUTAGE_BANKS_URL', raising=False)
    monkeypatch.delenv('CERTOUTAGE_OFFLINE', raising=False)
    co.clear_cache()
    yield
    co.clear_cache()


def _arrays(family, N, m):
    if family in ('GAIN', 'CHERNOFF'):
        data = dict(N=np.array(N, dtype=np.int64), B=np.array(gen.gain_period(N), dtype=np.int64))
        if family == 'GAIN' and m != 1:
            data['m'] = np.array(m, dtype=np.int64)
        if family == 'CHERNOFF':
            data['stride'] = np.array(8, dtype=np.int64)
        for method in (('exact', 'gauss') if family == 'GAIN' else ('chernoff',)):
            data[method + '_lo'] = np.zeros((1 << 19) + 1)
            data[method + '_hi'] = np.ones((1 << 19) + 1)
        return data
    size = 20481 if m == 1 else 1025
    data = {method: np.array([np.zeros(size), np.ones(size)])
            for method in (('exact', 'gauss') if family == 'SIG' else ('chernoff',))}
    if m == 1:
        data['levels'] = np.full(5121 if family == 'SIGC' else size, 9, dtype=np.int8)
    else:
        data['units128'] = np.arange(-4096, 4097, 8, dtype=np.int64)
    return data


def _packed_arrays(arrays):
    out = BytesIO()
    np.savez_compressed(out, **arrays)
    return out.getvalue()


def _tar_bytes(contents, changes=None):
    out = BytesIO()
    with tarfile.open(fileobj=out, mode='w', format=tarfile.PAX_FORMAT) as archive:
        for name, content in sorted(contents.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(content), 0o644, 0
            if changes is not None:
                info, content = changes(info, content)
                if info is None:
                    continue
            archive.addfile(info, BytesIO(content) if info.isreg() else None)
    raw = out.getvalue()
    return lzma.compress(raw, preset=0), len(raw)


@pytest.fixture(scope='session')
def synthetic(tmp_path_factory):
    """Production-shaped trivial bounds; compressed fixtures stay below 30 KB."""
    directory = tmp_path_factory.mktemp('bank_deposit')
    index = {'archives': [], 'embedded': fetch.bank_set()['embedded']}
    by_size = {}
    metadata = prep._metadata
    known = {}
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(prep, '_metadata', lambda name: known[name] if name in known else metadata(name))
        for N in (8, 12, 21, 64):
            wanted = {b['logical'] for a in fetch.bank_set()['archives'] if a['N'] == N for b in a['banks']}
            logicals = []
            for m, gain in COMBINATIONS:
                scope = gen.generation_scope(gain, m, N)
                logicals.extend(b['name'] for b in scope['banks'] if b['name'] in wanted)
            contents, banks = {}, []
            for logical in dict.fromkeys(logicals):
                family, parameters, generator = prep._identity(logical)
                name = _banks._generated_name(family, parameters, generator)
                content = _packed_arrays(_arrays(family, N, parameters['m']))
                meta = dict(schema=1, name=name, sha256=sha256(content).hexdigest(), bytes=len(content),
                            origin='generated', family=family, parameters=parameters, generator=generator,
                            certoutage_version=co.__version__, python_flint_version='0.9.0',
                            numpy_version=np.__version__, created_utc='2026-11-28T00:00:00Z')
                known[logical] = meta
                descriptor = _banks._canonical_json(meta)
                contents['generated/' + name] = content
                contents['generated/' + name[:-4] + '.json'] = descriptor
                banks.append(dict(stored_name=name, logical=logical, family=family, m=parameters['m'],
                                  sha256=meta['sha256'], bytes=len(content),
                                  descriptor_sha256=sha256(descriptor).hexdigest(), descriptor_bytes=len(descriptor)))
            packed, size = _tar_bytes(contents)
            filename = f'certoutage-banks-N{N:02}.tar.xz'
            (directory / filename).write_bytes(packed)
            index['archives'].append(dict(N=N, file=filename, bytes=len(packed), sha256=sha256(packed).hexdigest(),
                                          uncompressed_tar_bytes=size, banks=banks))
            by_size[N] = contents
    for name in fetch._LARGE_BANKS:
        (directory / name).write_bytes(_banks.verified_bytes(name))
    return directory, index, by_size


@pytest.fixture
def deposit(synthetic, monkeypatch):
    directory, index, contents = synthetic
    monkeypatch.setattr(fetch, 'bank_set', lambda: deepcopy(index))
    return directory, deepcopy(index), contents


@contextmanager
def _server(directory):
    state = {'requests': [], 'bytes': 0, 'headers': []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            state['requests'].append(self.path)
            state['headers'].append(dict(self.headers))
            mode, filename = self.path.lstrip('/').split('/', 1) if '/' in self.path.lstrip('/') else ('good', self.path.lstrip('/'))
            if mode in ('404', '500'):
                self.send_error(int(mode))
                return
            if mode in ('redirect', 'redirect-ok', 'unsafe') or mode.startswith('chain'):
                target = ('http://example.org/' + filename if mode == 'unsafe' else
                          '/good/' + filename if mode == 'redirect-ok' else
                          f'/chain{int(mode[5:]) - 1}/{filename}' if mode.startswith('chain') and int(mode[5:]) > 1 else
                          '/good/' + filename if mode == 'chain1' else self.path)
                self.send_response(302)
                self.send_header('Location', target)
                self.end_headers()
                return
            if mode == 'slow':
                sleep(0.1)
            try:
                body = (directory / filename).read_bytes()
            except FileNotFoundError:
                self.send_error(404)
                return
            pinned_size = len(body)
            if mode in ('truncated', 'incomplete'):
                body = body[:len(body) // 2]
            elif mode == 'altered':
                body = body[:-1] + bytes([body[-1] ^ 1])
            elif mode == 'oversized':
                body += b'extra'
            self.send_response(200)
            if mode != 'oversized':
                length = pinned_size + 1 if mode == 'large-header' else pinned_size if mode == 'incomplete' else len(body)
                self.send_header('Content-Length', str(length))
            self.end_headers()
            try:
                self.wfile.write(body)
                state['bytes'] += len(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def server(deposit):
    with _server(deposit[0]) as running:
        yield running


def _no_partial_install():
    assert not list(_banks.cache_dir().rglob('*.part'))
    assert not list((_banks.cache_dir() / 'generated').glob('*'))


def _disable_generators(monkeypatch):
    for module, names in ((gen, ('gain_arrays', 'signal_arrays', 'nakagami_signal_arrays', 'chernoff_signal_arrays')),
                          (ch, ('chernoff_arrays',))):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)


def _ready(N):
    for m, gain in COMBINATIONS:
        assert all(row.origin != 'missing' for row in co.prepare(co.Model(N=N, m=m), gain=gain, dry_run=True))


def test_no_network_without_explicit_fetch(monkeypatch):
    for name in ('socket', 'create_connection', 'getaddrinfo'):
        monkeypatch.setattr(socket, name, forbidden)
    monkeypatch.setattr(fetch, 'fetch_banks', forbidden)
    model = co.Model(convention='C-INR')
    a = co.required_snr(model, 1, '1e-5')
    co.outage_enclosure(model, 1, 0)
    co.floor(model, 1)
    co.compare_approximations(model, 1, '1e-5')
    co.largest_interferer_bound(model, 1)
    co.largest_interferer_bound(co.Model(N=8), 1)
    co.threshold_difference(a, a)
    co.prepare(model)
    co.prepare(co.Model(N=21), dry_run=True)
    co.prepare(co.Model(N=21), fetch=True, dry_run=True)
    with pytest.raises(co.BankNotAvailable, match='fetch_banks\\(21\\).*MB.*prepare'):
        co.floor(co.Model(N=21), 1)
    assert not _banks.cache_dir().exists()


def test_import_without_network_or_lzma():
    code = '''
import sys, socket
sys.modules['lzma'] = None
def refuse(*args, **kwargs):
    raise RuntimeError('Network access during import')
socket.socket = socket.create_connection = socket.getaddrinfo = refuse
import certoutage
assert callable(certoutage.fetch_banks)
'''
    result = subprocess.run([sys.executable, '-c', code], env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert not _banks.cache_dir().exists()


@pytest.mark.parametrize('value', ['1', 'yes', 'false'])
def test_offline_precedes_every_socket(monkeypatch, value):
    monkeypatch.setenv('CERTOUTAGE_OFFLINE', value)
    for name in ('socket', 'create_connection', 'getaddrinfo'):
        monkeypatch.setattr(socket, name, forbidden)
    with pytest.raises(co.BankDownloadError, match='CERTOUTAGE_OFFLINE.*directory='):
        co.fetch_banks(21, url='https://example.org')
    assert not _banks.cache_dir().exists()


def test_published_mirrors():
    assert fetch.MIRRORS == (
        'https://zenodo.org/records/24630633/files/{file}?download=1',
        'https://github.com/HubHubHubHubHub/certoutage-banks/releases/download/bankset-2026-11-28/{file}')
    for base in fetch.MIRRORS:
        fetch._check_url(base.replace('{file}', 'MANIFEST.json'))


def test_default_mirrors_in_order_without_url(monkeypatch):
    seen = []
    class Refusing:
        def open(self, request, timeout):
            seen.append(request.full_url)
            raise OSError('refused by the test')
    monkeypatch.setattr(fetch, '_opener', Refusing)
    with pytest.raises(co.BankDownloadError, match='All bank locations failed') as error:
        co.fetch_banks(21)
    archive = next(a['file'] for a in fetch.bank_set()['archives'] if a['N'] == 21)
    assert seen == [base.replace('{file}', archive) for base in fetch.MIRRORS]
    assert all(url in str(error.value) for url in seen)
    _no_partial_install()


def test_no_published_location(monkeypatch):
    monkeypatch.setattr(fetch, 'MIRRORS', ())
    for name in ('socket', 'create_connection', 'getaddrinfo'):
        monkeypatch.setattr(socket, name, forbidden)
    with pytest.raises(co.BankDownloadError, match='No published.*url=.*CERTOUTAGE_BANKS_URL.*directory='):
        co.fetch_banks(21)
    assert not _banks.cache_dir().exists()


@pytest.mark.parametrize('url', ['http://example.org/', 'file:///tmp/', 'ftp://example.org/'])
def test_refused_scheme_before_socket(monkeypatch, url):
    for name in ('socket', 'create_connection', 'getaddrinfo'):
        monkeypatch.setattr(socket, name, forbidden)
    with pytest.raises(co.BankDownloadError, match='HTTPS is required') as error:
        co.fetch_banks(21, url=url)
    assert url in str(error.value)
    _no_partial_install()


@pytest.mark.parametrize('args,kwargs', [((), {}), ((7,), {}), ((65,), {}), ((True,), {}), ((8.0,), {}),
                                         ((8,), {'url': 'https://example.org', 'directory': '.'}),
                                         ((8,), {'timeout': 0}), ((8,), {'timeout': float('nan')})])
def test_argument_validation(args, kwargs):
    with pytest.raises(ValueError):
        co.fetch_banks(*args, **kwargs)
    assert not _banks.cache_dir().exists()


def test_http_success_and_short_circuit(server, deposit, monkeypatch):
    base, state = server
    _disable_generators(monkeypatch)
    rows = co.fetch_banks(co.Model(N=21), 21, url=base + '/good/{file}')
    assert len(state['requests']) == 1
    assert len(rows) == 9 and len({r.logical for r in rows}) == 9
    assert all(row.estimated_seconds is None and row.seconds > 0 for row in rows)
    assert {r.origin for r in rows} == {'fetched', 'embedded'}
    for name, data in deposit[2][21].items():
        assert (_banks.cache_dir() / name).read_bytes() == data
    before = {p: p.stat().st_mtime_ns for p in _banks.cache_dir().rglob('*') if p.is_file()}
    previous = state['bytes']
    repeated = co.fetch_banks(21, url=base + '/500')
    assert {r.origin for r in repeated} == {'cached', 'embedded'}
    assert state['bytes'] == previous and len(state['requests']) == 1
    assert before == {p: p.stat().st_mtime_ns for p in before}
    _ready(21)
    for m, gain in COMBINATIONS:
        point = co.outage_enclosure(co.Model(N=21, m=m), 1, 0, gain=gain)
        assert 0 <= point.lower <= point.upper <= 1
        assert point.contract.source == 'generated-banks'
    assert state['headers'][0]['User-Agent'] == 'certoutage/' + co.__version__
    assert 'Proxy-Authorization' not in state['headers'][0]
    assert not list(_banks.cache_dir().rglob('*.part'))


def test_directory_offline_and_order(deposit, monkeypatch):
    monkeypatch.setenv('CERTOUTAGE_OFFLINE', '1')
    for name in ('socket', 'create_connection', 'getaddrinfo'):
        monkeypatch.setattr(socket, name, forbidden)
    _disable_generators(monkeypatch)
    rows = co.fetch_banks(21, 12, 21, directory=deposit[0])
    installed = [r for r in rows if r.origin == 'fetched']
    assert [prep._spec(r.logical)[1] for r in installed] == [12] * 2 + [21] * 8
    for N in (12, 21):
        for name, content in deposit[2][N].items():
            assert (_banks.cache_dir() / name).read_bytes() == content
        _ready(N)


@pytest.mark.parametrize('mode', ['404', '500', 'slow', 'redirect', 'unsafe', 'incomplete', 'chain6'])
def test_transport_failure_is_named_and_clean(server, mode, monkeypatch):
    base, state = server
    resolve = socket.getaddrinfo
    def local_only(host, *args, **kwargs):
        if host not in ('127.0.0.1', '::1', 'localhost'):
            raise AssertionError('A redirect attempted a non-loopback connection')
        return resolve(host, *args, **kwargs)
    monkeypatch.setattr(socket, 'getaddrinfo', local_only)
    with pytest.raises(co.BankDownloadError) as error:
        co.fetch_banks(12, url=base + '/' + mode, timeout=0.02 if mode == 'slow' else 2)
    assert base in str(error.value) and error.value.__cause__ is not None
    assert not any('example.org' in path for path in state['requests'])
    _no_partial_install()


def test_refused_connection():
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    with pytest.raises(co.BankDownloadError, match='127.0.0.1'):
        co.fetch_banks(12, url=f'http://127.0.0.1:{port}', timeout=0.1)
    _no_partial_install()


def test_transport_retries_mirror_and_priority(server, monkeypatch):
    base, state = server
    monkeypatch.setattr(fetch, 'MIRRORS', (base + '/500', base + '/good'))
    co.fetch_banks(12)
    assert [p.split('/')[1] for p in state['requests']] == ['500', 'good']
    monkeypatch.setenv('CERTOUTAGE_BANKS_URL', base + '/404')
    co.fetch_banks(8, url=base + '/redirect-ok')
    assert [p.split('/')[1] for p in state['requests']][-2:] == ['redirect-ok', 'good']
    with pytest.raises(co.BankDownloadError, match='404'):
        co.fetch_banks(21)
    assert state['requests'][-1].startswith('/404/')


def test_five_redirects_allowed(server):
    base, state = server
    co.fetch_banks(12, url=base + '/chain5')
    assert len(state['requests']) == 6


@pytest.mark.parametrize('mode', ['truncated', 'altered', 'oversized', 'large-header'])
def test_integrity_failure_never_tries_next_mirror(server, monkeypatch, mode):
    base, state = server
    monkeypatch.setattr(fetch, 'MIRRORS', (base + '/' + mode, base + '/good'))
    with pytest.raises(co.IntegrityError):
        co.fetch_banks(12)
    assert len(state['requests']) == 1
    _no_partial_install()


@pytest.mark.parametrize('damage', ['parent', 'absolute', 'backslash', 'symlink', 'hardlink', 'directory',
                                   'fifo', 'device', 'extra', 'missing', 'duplicate', 'digest', 'size', 'unreadable'])
def test_forged_pinned_archive_rejected(deposit, monkeypatch, tmp_path, damage):
    directory, index, by_size = deposit
    pin = next(a for a in index['archives'] if a['N'] == 12)
    contents = dict(by_size[12])
    target = next(n for n in contents if n.endswith('.npz'))
    if damage == 'extra':
        contents['generated/EXTRA_0000000000000000.npz'] = b'extra'
    if damage == 'missing':
        del contents[target]
    if damage == 'digest':
        contents[target] = contents[target][:-1] + bytes([contents[target][-1] ^ 1])
    def change(info, data):
        if info.name == target:
            if damage in ('parent', 'absolute', 'backslash'):
                info.name = {'parent': '../outside', 'absolute': '/outside', 'backslash': 'generated\\outside'}[damage]
            if damage in ('symlink', 'hardlink', 'directory', 'fifo', 'device'):
                info.type = {'symlink': tarfile.SYMTYPE, 'hardlink': tarfile.LNKTYPE, 'directory': tarfile.DIRTYPE,
                             'fifo': tarfile.FIFOTYPE, 'device': tarfile.CHRTYPE}[damage]
                info.linkname = '../outside'
            if damage == 'size':
                info.size -= 1
                data = data[:-1]
            if damage == 'duplicate':
                info.name = next(n for n in contents if n != target)
        return info, data
    packed, tar_size = _tar_bytes(contents, change)
    if damage == 'unreadable':
        packed = b'not an xz archive'
    pin.update(bytes=len(packed), sha256=sha256(packed).hexdigest(), uncompressed_tar_bytes=tar_size)
    malicious = tmp_path / 'malicious'
    malicious.mkdir()
    (malicious / pin['file']).write_bytes(packed)
    monkeypatch.setattr(fetch, 'bank_set', lambda: index)
    with pytest.raises(co.IntegrityError):
        co.fetch_banks(12, directory=malicious)
    _no_partial_install()
    assert not (tmp_path / 'outside').exists()


def test_archive_digest_itself_is_checked(deposit, monkeypatch):
    directory, index, _ = deposit
    next(a for a in index['archives'] if a['N'] == 12)['sha256'] = '0' * 64
    monkeypatch.setattr(fetch, 'bank_set', lambda: index)
    with pytest.raises(co.IntegrityError, match='SHA-256'):
        co.fetch_banks(12, directory=directory)
    _no_partial_install()


def test_all_members_checked_before_any_write(deposit, monkeypatch):
    directory, index, _ = deposit
    next(a for a in index['archives'] if a['N'] == 12)['banks'][-1]['descriptor_sha256'] = 'f' * 64
    monkeypatch.setattr(fetch, 'bank_set', lambda: index)
    monkeypatch.setattr(_banks, '_atomic_write', forbidden)
    with pytest.raises(co.IntegrityError):
        co.fetch_banks(12, directory=directory)
    _no_partial_install()


def test_missing_lzma_is_named(deposit, monkeypatch):
    monkeypatch.setitem(sys.modules, 'lzma', None)
    with pytest.raises(co.BankDownloadError, match='lzma'):
        co.fetch_banks(12, directory=deposit[0])
    _no_partial_install()


def test_interrupted_stream_cleans_part(deposit, monkeypatch):
    def interrupt(source, target, pin, location, declared):
        target.write(b'partial')
        raise KeyboardInterrupt
    monkeypatch.setattr(fetch, '_copy_stream', interrupt)
    with pytest.raises(KeyboardInterrupt):
        co.fetch_banks(12, directory=deposit[0])
    _no_partial_install()


def _install_one(deposit, N=12):
    pin = next(a for a in deposit[1]['archives'] if a['N'] == N)
    bank = next(b for b in pin['banks'] if b['family'] == 'CHERNOFF')
    name = bank['stored_name']
    target = _banks.cache_dir() / 'generated' / name
    target.parent.mkdir(parents=True)
    target.write_bytes(deposit[2][N]['generated/' + name])
    target.with_suffix('.json').write_bytes(deposit[2][N]['generated/' + name[:-4] + '.json'])
    return target


def test_existing_valid_different_bank_is_preserved(deposit):
    path = _install_one(deposit)
    data = {k: v.copy() for k, v in _banks.arrays(path.name).items()}
    data['chernoff_lo'][0] = 0.125
    content = _packed_arrays(data)
    path.write_bytes(content)
    descriptor = path.with_suffix('.json')
    meta = json.loads(descriptor.read_text())
    meta.update(sha256=sha256(content).hexdigest(), bytes=len(content))
    descriptor.write_bytes(_banks._canonical_json(meta))
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (path, descriptor)]
    with pytest.warns(RuntimeWarning, match='Preserving existing valid bank'):
        with pytest.raises(co.BankNotAvailable, match='every combination ready.*SIG_C_12.*different pinned bytes'):
            co.fetch_banks(12, directory=deposit[0])
    assert before == [(p.read_bytes(), p.stat().st_mtime_ns) for p in (path, descriptor)]


@pytest.mark.parametrize('damage', ['bank', 'descriptor'])
def test_existing_corruption_is_never_repaired(deposit, damage):
    path = _install_one(deposit)
    (path if damage == 'bank' else path.with_suffix('.json')).write_bytes(b'broken')
    paths = list(path.parent.iterdir())
    before = {p: p.read_bytes() for p in paths}
    with pytest.raises(co.IntegrityError):
        co.fetch_banks(12, directory=deposit[0])
    assert before == {p: p.read_bytes() for p in path.parent.iterdir()}
    assert not (_banks.cache_dir() / 'fetched').exists()


@pytest.mark.parametrize('remaining', ['bank', 'descriptor'])
def test_incomplete_pair_is_completed(deposit, remaining):
    path = _install_one(deposit)
    (path.with_suffix('.json') if remaining == 'bank' else path).unlink()
    co.fetch_banks(12, directory=deposit[0])
    _ready(12)
    for name, content in deposit[2][12].items():
        assert (_banks.cache_dir() / name).read_bytes() == content


def _embedded_queries():
    result = []
    for m in (1, 2, 3):
        for lam in (0, '0.1'):
            model = co.Model(N=8, m=m, lam=lam)
            result.append(co.outage_enclosure(model, 1, -10))
    result.append(co.largest_interferer_bound(co.Model(N=8, m=2), 1))
    return result


def test_fetched_copies_preserve_every_contract(deposit, monkeypatch):
    before = _embedded_queries()
    _disable_generators(monkeypatch)
    with _banks._withhold_embedded(*fetch._LARGE_BANKS):
        with pytest.raises(co.BankNotAvailable, match=r'fetch_banks\(8\)'):
            co.outage_enclosure(co.Model(N=8, lam=0), 1, 20)
        rows = co.fetch_banks(8, 64, directory=deposit[0])
        assert {p.name for p in (_banks.cache_dir() / 'fetched').glob('*.npz')} == set(fetch._LARGE_BANKS)
        for name in fetch._LARGE_BANKS:
            assert _banks._resolve(name) == ((deposit[0] / name).read_bytes(), 'fetched')
        assert all(r.origin == 'fetched' for r in rows)
        after = _embedded_queries()
        assert [(r.lower.hex(), r.upper.hex(), r.contract) for r in before] == [
            (r.lower.hex(), r.upper.hex(), r.contract) for r in after]
        _ready(8)
        _ready(64)
        assert 'missing' not in {r.origin for r in co.prepare(co.Model(N=8), dry_run=True)}
        repeated = co.fetch_banks(8, directory=deposit[0])
        assert all(r.origin == 'cached' for r in repeated)


def test_fetched_tampering_is_checked_on_next_query(deposit):
    with _banks._withhold_embedded(*fetch._LARGE_BANKS):
        co.fetch_banks(8, directory=deposit[0])
        co.outage_enclosure(co.Model(N=8, lam=0), 1, 20)
        path = _banks.cache_dir() / 'fetched/m1_N8.npz'
        path.write_bytes(b'corrupt')
        with pytest.raises(co.IntegrityError, match='m1_N8.npz'):
            co.outage_enclosure(co.Model(N=8, lam=0), 1, 20)
        assert path.read_bytes() == b'corrupt'


def test_package_files_take_priority_over_fetched(deposit):
    directory = _banks.cache_dir() / 'fetched'
    directory.mkdir(parents=True)
    (directory / 'm1_N8.npz').write_bytes(b'corrupt')
    assert _banks._resolve('m1_N8.npz')[1] == 'embedded'
    assert prep._metadata('m1_N8.npz')['origin'] == 'embedded'


def test_actual_absent_resource_uses_fetched(deposit, monkeypatch, tmp_path):
    root = _banks.files('certoutage')
    class Resources:
        def joinpath(self, *parts):
            return tmp_path / 'absent' if Path(*parts).name == 'm1_N8.npz' else root.joinpath(*parts)
    monkeypatch.setattr(_banks, 'files', lambda _: Resources())
    with pytest.raises(co.BankNotAvailable, match=r'fetch_banks\(8\)'):
        co.outage_enclosure(co.Model(N=8, lam=0), 1, 20)
    co.fetch_banks(8, directory=deposit[0])
    assert _banks._resolve('m1_N8.npz')[1] == 'fetched'


def test_pinned_index_and_embedded_digests():
    content = fetch.files('certoutage').joinpath('data/BANK_SET.json').read_bytes()
    assert sha256(content).hexdigest() == fetch.BANK_SET_SHA256
    index = fetch.bank_set()
    assert len(index['archives']) == 55 and len(index['embedded']) == 5
    for row in index['embedded']:
        assert {key: row[key] for key in ('sha256', 'bytes')} == {
            key: _banks.manifest()[row['file']][key] for key in ('sha256', 'bytes')}


def test_changed_index_is_rejected(monkeypatch, tmp_path):
    corrupt = tmp_path / 'BANK_SET.json'
    corrupt.write_bytes(b'{"archives": []}')
    class Resources:
        def joinpath(self, *parts):
            return corrupt
    monkeypatch.setattr(fetch, 'files', lambda _: Resources())
    with pytest.raises(co.IntegrityError, match='BANK_SET.json'):
        co.fetch_banks(21)
    assert not _banks.cache_dir().exists()


def test_all_pinned_names_match_preparation_identities(monkeypatch):
    index = fetch.bank_set()
    known = {row['logical']: row for a in index['archives'] for row in a['banks']}
    original = prep._metadata
    monkeypatch.setattr(prep, '_metadata', lambda name: known[name] if name in known else original(name))
    for archive in index['archives']:
        for bank in archive['banks']:
            assert prep._stored_name(bank['logical']) == bank['stored_name']


def test_prepare_fetch_is_explicit(server, monkeypatch):
    base, state = server
    monkeypatch.setenv('CERTOUTAGE_BANKS_URL', base + '/good')
    _disable_generators(monkeypatch)
    plan = co.prepare(co.Model(N=12), gain='chernoff', fetch=True, dry_run=True)
    assert any(r.origin == 'missing' for r in plan) and state['requests'] == []
    rows = co.prepare(co.Model(N=12), gain='chernoff', fetch=True)
    assert all(r.origin in ('embedded', 'cached') for r in rows)
    assert len(state['requests']) == 1
    _ready(12)


def test_prepare_fetch_error_never_starts_generation(server, monkeypatch):
    base, _ = server
    monkeypatch.setenv('CERTOUTAGE_BANKS_URL', base + '/500')
    _disable_generators(monkeypatch)
    with pytest.raises(co.BankDownloadError):
        co.prepare(co.Model(N=21), fetch=True)
    _no_partial_install()


def test_postcondition_is_enforced(deposit, monkeypatch):
    directory, index, _ = deposit
    index['archives'] = []
    monkeypatch.setattr(fetch, 'bank_set', lambda: index)
    with pytest.raises(co.BankNotAvailable, match='every combination ready.*SIG_C_12'):
        co.fetch_banks(12, directory=directory)


@pytest.mark.skipif(not os.environ.get('CERTOUTAGE_BANKSET_DIR'), reason='explicit real deposit control')
@pytest.mark.parametrize('withheld', [False, True])
def test_real_bank_set_over_local_http(monkeypatch, withheld):
    directory = Path(os.environ['CERTOUTAGE_BANKSET_DIR'])
    _disable_generators(monkeypatch)
    started = perf_counter()
    with _server(directory) as (base, state):
        with _banks._withhold_embedded(*fetch._LARGE_BANKS) if withheld else nullcontext():
            rows = co.fetch_banks(8, 21, 63, url=base + '/good')
            for N in (8, 21, 63):
                _ready(N)
                for m, gain in COMBINATIONS:
                    point = co.outage_enclosure(co.Model(N=N, m=m), 1, 0, gain=gain)
                    assert 0 <= point.lower <= point.upper <= 1
                    if N != 8 or gain == 'chernoff':
                        assert point.contract.source == 'generated-banks'
            print(json.dumps(dict(withheld=withheld, seconds=perf_counter()-started,
                                  transferred_bytes=state['bytes'], installed_bytes=sum(r.bytes for r in rows if r.origin=='fetched'),
                                  requests=len(state['requests']))))


@pytest.mark.skipif(os.environ.get('CERTOUTAGE_REAL_MIRRORS') != '1', reason='explicit control of the published mirrors')
@pytest.mark.parametrize('withheld', [False, True])
@pytest.mark.parametrize('mirror', ['default', 'zenodo', 'github'])
def test_real_published_mirrors(monkeypatch, withheld, mirror):
    url = {'default': None, 'zenodo': fetch.MIRRORS[0], 'github': fetch.MIRRORS[1]}[mirror]
    _disable_generators(monkeypatch)
    started = perf_counter()
    with _banks._withhold_embedded(*fetch._LARGE_BANKS) if withheld else nullcontext():
        rows = co.fetch_banks(8, 21, 63, url=url)
        assert not list(_banks.cache_dir().rglob('*.part'))
        for N in (8, 21, 63):
            _ready(N)
            for m, gain in COMBINATIONS:
                point = co.outage_enclosure(co.Model(N=N, m=m), 1, 0, gain=gain)
                assert 0 <= point.lower <= point.upper <= 1
                if N != 8 or gain == 'chernoff':
                    assert point.contract.source == 'generated-banks'
        print(json.dumps(dict(mirror=mirror, withheld=withheld, seconds=perf_counter() - started,
                              fetched=sum(r.origin == 'fetched' for r in rows),
                              installed_bytes=sum(r.bytes for r in rows if r.origin == 'fetched'))))


@pytest.mark.parametrize('kind', [tarfile.SYMTYPE, tarfile.LNKTYPE], ids=['symlink', 'hardlink'])
def test_link_with_matching_target_bytes_is_rejected(deposit, monkeypatch, tmp_path, kind):
    directory, index, by_size = deposit
    pin = next(a for a in index['archives'] if a['N'] == 12)
    source = next(b for b in pin['banks'] if b['family'] == 'CHERNOFF')
    target = next(b for b in pin['banks'] if b['family'] == 'SIGC')
    contents = dict(by_size[12])
    source_name = 'generated/' + source['stored_name']
    target_name = 'generated/' + target['stored_name']
    source.update(bytes=target['bytes'], sha256=target['sha256'])
    descriptor_name = source_name[:-4] + '.json'
    meta = json.loads(contents[descriptor_name])
    meta.update(bytes=source['bytes'], sha256=source['sha256'])
    contents[descriptor_name] = _banks._canonical_json(meta)
    source.update(descriptor_bytes=len(contents[descriptor_name]),
                  descriptor_sha256=sha256(contents[descriptor_name]).hexdigest())
    contents[source_name] = contents[target_name]
    def link(info, data):
        if info.name == source_name:
            info.type = kind
            info.linkname = target['stored_name'] if kind == tarfile.SYMTYPE else target_name
        return info, data
    packed, tar_size = _tar_bytes(contents, link)
    pin.update(bytes=len(packed), sha256=sha256(packed).hexdigest(), uncompressed_tar_bytes=tar_size)
    path = tmp_path / pin['file']
    path.write_bytes(packed)
    monkeypatch.setattr(fetch, 'bank_set', lambda: index)
    with pytest.raises(co.IntegrityError, match='Invalid archive member'):
        co.fetch_banks(12, directory=tmp_path)
    _no_partial_install()



def test_directory_and_scheme_checks_need_no_socket_imports(deposit):
    code = r"""
import json, socket, sys
for name in ('socket', 'create_connection', 'getaddrinfo'):
    setattr(socket, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError('Network attempted')))
import certoutage as co
from certoutage import _fetch
_fetch.bank_set = lambda: json.loads(sys.argv[2])
for location in ('http://example.org', 'file:///unavailable', 'ftp://example.org'):
    try:
        co.fetch_banks(12, url=location)
    except co.BankDownloadError:
        pass
    else:
        raise AssertionError('Forbidden scheme accepted')
try:
    co.fetch_banks(12, directory=sys.argv[1] + '/absent')
except co.BankDownloadError:
    pass
else:
    raise AssertionError('Missing directory accepted')
co.fetch_banks(12, directory=sys.argv[1])
"""
    result = subprocess.run([sys.executable, '-c', code, str(deposit[0]), json.dumps(deposit[1])],
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), capture_output=True,
                            text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    _ready(12)
