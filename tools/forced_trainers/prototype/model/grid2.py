"""Late-game spread under different exp scaling: full-clear lead / skip-all lead at key bosses."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'grid.py')).read()
exec(compile(src.split("print(f\"{'1.5x'")[0].replace("os.path.abspath(__file__)", repr(os.path.join(HERE, 'grid.py'))), 'grid.py', 'exec'))

for label, extra in [('flat (no scaling)', {'scaled_exp': False})]:
    for exp, pct, pen in [('1.5x on', 0, 'soft 30%/6/30%'), ('1.5x on', 0, 'today 15%/4/10%'), ('1.5x off', 0, 'today 15%/4/10%')]:
        tr = raised(pct)
        knobs = {**base, 'trainer_exp': exp, **PENALTIES[pen], **extra}
        full, skip = run(tr, knobs, False), run(tr, knobs, True)
        row = []
        for b in ('TRAINER_ROXANNE_1', 'TRAINER_WATTSON_1', 'TRAINER_NORMAN_1', 'TRAINER_WINONA_1', 'TRAINER_JUAN_1', 'TRAINER_WALLACE'):
            fl, sl = full[b]['levels'][0], skip[b]['levels'][0]
            row.append(f"{b[8:14]} {fl}/{sl} ({(fl - sl) * 100 / fl:.0f}%)")
        print(f"{label:18} {exp} +{pct}% | " + ' | '.join(row))
