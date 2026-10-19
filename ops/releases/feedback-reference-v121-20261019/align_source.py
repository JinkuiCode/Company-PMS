"""Align accepted source records while preserving the fixed running payload."""
import argparse
import json
import re
from pathlib import Path
import windows_update as w
import program_update as u
from publish import synchronize_checkout, validate_evidence, APPROVAL, BUILD


def validate_scope(scope, pins):
    u.check(set(scope) == {'baseline', 'target', 'files', 'bundle_sha256'}, 'Unexpected alignment scope')
    u.check(scope['baseline'] == BUILD == pins['commit'], 'Alignment baseline differs')
    u.check(re.fullmatch('[0-9a-f]{40}', scope['target']) is not None, 'Invalid source target')
    u.check(bool(scope['files']), 'Empty source scope')
    for name, digest in scope['files'].items():
        u.check(name == 'change.md' or name.startswith(('docs/', 'ops/releases/feedback-reference-v121-20261019/')), 'Non-maintenance source path')
        u.check(re.fullmatch('[0-9a-f]{64}', digest) is not None, 'Invalid source digest')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approval', required=True)
    args = parser.parse_args()
    u.check(args.approval == APPROVAL, 'Concrete alignment approval required')
    c = w.WindowsUpdate(APPROVAL)
    try:
        from app.services.runtime_release import load_runtime_manifest
        manifest = load_runtime_manifest()
        acceptance = json.loads((w.HERE / 'browser-acceptance.json').read_text(encoding='utf-8'))
        validate_evidence(c.state, acceptance, manifest)
        publication = json.loads((w.HERE / 'v121-publication-state.json').read_text(encoding='utf-8'))
        u.check(publication.get('phase') == 'publication-and-mail-complete' and publication.get('version') == 'v1.2.1', 'Publication not complete')
        scope = json.loads((w.HERE / 'final-source-scope.json').read_text(encoding='utf-8'))
        validate_scope(scope, c.pins)
        state_path = w.HERE / 'final-source-alignment.json'
        u.check(not state_path.exists(), 'Alignment already recorded; inspect instead of repeating')
        bundle = w.HERE / 'final-source.bundle'
        u.check(u.hashfile(bundle) == scope['bundle_sha256'], 'Final bundle differs')
        c.files.verify_installed()
        before = w.process()
        w.verify_process(before, c.state['normal_process'], c.cfg['pythonExe'])
        payload = u.read_package(w.HERE / 'candidate.zip', c.pins)
        fixed = {n for n in payload if n.startswith(('backend/', 'ops/windows/', 'frontend/dist/')) or n == 'release.json'}

        def verify_runtime():
            c.files.config_guard()
            u.check(all((w.ROOT / name).read_bytes() == payload[name] for name in fixed), 'Running payload differs')
            u.check(u.tree(w.ROOT / 'frontend/dist') == {n[len('frontend/dist/'):]: u.digest(payload[n]) for n in fixed if n.startswith('frontend/dist/')}, 'Frontend tree differs')
            u.check(w.process() == before, 'Normal process changed')
            with c.engine.connect() as connection:
                u.check(connection.execute(c.text('SELECT revision FROM dbo.pms_database_revision WHERE id=1')).scalar_one() == c.pins['schema'], 'Schema differs')
            with c.opener.open('http://127.0.0.1:8000/api/health', timeout=8) as response:
                u.check(json.load(response).get('status') == 'ok', 'Normal health failed')

        verify_runtime()
        u.git(w.ROOT, 'bundle', 'create', str(w.HERE / 'before-final-source.bundle'), 'HEAD')
        paths = synchronize_checkout(w.ROOT, bundle, BUILD, scope['target'], fixed, set(scope['files']))
        u.check(set(paths) == set(scope['files']), 'Final source path set differs')
        u.check(all(u.hashfile(w.ROOT / name) == digest for name, digest in scope['files'].items()), 'Final source bytes differ')
        verify_runtime()
        result = dict(head=scope['target'], runtime_commit=BUILD, version='v1.2.1', schema=c.pins['schema'], pid=before['pid'], application_bytes_unchanged=True, protected_configuration_unchanged=True, no_restart=True, publication_complete=True)
        u.save(state_path, result)
        print('V121_SOURCE_ALIGNED ' + json.dumps(result), flush=True)
    finally:
        c.engine.dispose()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('SOURCE_ALIGNMENT_STOPPED ' + type(error).__name__ + '; preserve evidence; no automatic retry', flush=True)
        raise SystemExit(1)
