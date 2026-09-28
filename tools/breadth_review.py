"""Sequential, reproducible solo and genre review using both audit tools."""
import argparse
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yaml
from tools.album_diversity import album_configs, fingerprint, report
from tools.rhythm_review import inspect
from produzre.config.load import load_root_config


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--configs', type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    corpus = []
    if args.configs:
        corpus = json.loads(args.configs.read_text())
    else:
        for genre, instrument in [('pop','drums'), ('country','acoustic_gtr'), ('pop','lead_gtr')]:
            corpus += album_configs(genre, 5, instruments=[instrument])
        for genre in ('country', 'funk', 'reggae', 'jazz', 'pop', 'metal'):
            corpus += album_configs(genre, 10)
        for meter in ('3/4', '6/8', '7/8'):
            cfg = album_configs('jazz' if meter == '3/4' else 'rock', 1, meter=meter)[0]
            cfg['song']['title'] = 'Meter ' + meter.replace('/', '_')
            corpus.append(cfg)
    (args.out/'corpus.json').write_text(json.dumps(corpus, indent=2))
    metrics, albums = {}, {}
    for cfg in corpus:
        title = cfg['song']['title'].replace(' ', '_')
        cfg['song']['exports_root'] = str(args.out.resolve()/'renders')
        path = args.out/(title + '.yaml')
        path.write_text(yaml.safe_dump(cfg, sort_keys=False))
        data = inspect(load_root_config(str(path)))
        metrics[title] = data
        num, den = map(int, cfg['song']['meter'].split('/'))
        fp = fingerprint(data['export'], '', num*4/den)
        group = cfg['song']['genre'] + ':' + ','.join(n for n in cfg['sections']['chorus']['instruments'] if n != 'harmony')
        if not title.startswith('Meter'):
            albums.setdefault(group, []).append(fp)
        (args.out/'metrics.json').write_text(json.dumps(metrics))
        print(title, flush=True)
    (args.out/'albums.json').write_text(json.dumps({g:report(fps) for g,fps in albums.items()}, indent=2))


if __name__ == '__main__':
    logging.basicConfig(level=logging.ERROR)
    main()
