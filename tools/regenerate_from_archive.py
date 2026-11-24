"""Copie les générateurs v7 avant exécution locale. Aucune soumission de job.

Les sorties ne sont jamais écrites dans l'archive. Le répertoire de travail
est nouveau. La régénération complète peut durer longtemps ; elle est séparée
de l'API normale. Voir docs/REGENERATION.md.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--kind', choices=['signal', 'chernoff', 'nakagami', 'largest'], required=True)
    p.add_argument('--N', type=int, default=24)
    p.add_argument('--m', type=int, choices=[2, 3], default=2)
    args = p.parse_args()
    archive, work = args.archive.resolve(), args.output.resolve()
    if work == archive or archive in work.parents:
        p.error('la sortie ne doit jamais appartenir à l’archive')
    if work.exists():
        p.error('le répertoire de sortie doit être nouveau')
    if args.N not in [8,12,16,20,24,32,48,64]:
        p.error('N hors périmètre de la phase 1')
    source = archive / ('campaigns/t20/code' if args.kind == 'nakagami' else 'ppp/code')
    selected = (['commun.py','amplitude.py','kernel.py','t4_backend.py','thermal.py','grouped.py','calcul_thermique.py']
                if args.kind == 'nakagami' else
                ['commun.py','thermal_backend.py','amplitude.py','grouped.py','preparer_signal.py',
                 'preparer_chernoff.py','chernoff.py','ppp.py','oracles.py','minorants.py'])
    code = work / 'code'
    code.mkdir(parents=True)
    for folder in ['banques','resultats','entrees']:
        (work / folder).mkdir()
    changes = []
    for name in selected:
        src = source / name
        text = src.read_text()
        patched = text.replace("os.environ['SLURM_JOB_ID']", "os.environ.get('SLURM_JOB_ID')")
        (code / name).write_text(patched)
        changes.append(dict(source=str(src.relative_to(archive)),
                            source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
                            optional_scheduler_metadata=patched != text))
    (work / 'COPIES.json').write_text(json.dumps(changes, indent=2))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    env.pop('PYTHONPATH', None)

    def run(name: str, *arguments: object) -> None:
        subprocess.run([sys.executable, str(code/name), *map(str,arguments)], cwd=work, env=env, check=True)

    if args.kind == 'largest':
        # This command regenerates the distribution of J_max and its integral;
        # it intentionally reuses the integrity-checked useful-gain bank.
        from certoutage._banks import arrays
        np = __import__('numpy')
        np.savez(work/f'banques/SIG_{args.N}.npz', **arrays(f'SIG_{args.N}.npz'))
        shutil.copyfile(archive/'ppp/entrees/campaign_pp_PLANCHERS.csv', work/'entrees/campaign_pp_PLANCHERS.csv')
        run('minorants.py', args.N)
    elif args.kind == 'nakagami':
        shutil.copyfile(archive/'campaigns/t20/banques/commun.npz', work/'banques/commun.npz')
        run('amplitude.py', args.m, args.N)
        run('calcul_thermique.py', args.m, args.N)
    else:
        subprocess.run([sys.executable, '-c',
                        "import sys; sys.path.insert(0, 'code'); from thermal_backend import common; common()"],
                       cwd=work, env=env, check=True)
        run('amplitude.py', args.N)
        run('preparer_chernoff.py' if args.kind == 'chernoff' else 'preparer_signal.py', args.N)


if __name__ == '__main__':
    main()
