# coding: utf-8
"""Run with python -m curs.kol_intent --config config.yml."""

import argparse
import logging
from pathlib import Path

import pandas as pd

from curs.kol_intent.data import load_public_prices
from curs.kol_intent.report import analyze, export_report
from curs.utils.config import load_yaml


def main() -> None:
    """Resolve research paths relative to the selected YAML configuration file."""
    parser = argparse.ArgumentParser(description='Offline KOL intent research')
    parser.add_argument('--config', type=Path, default=Path('config.yml'))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s - %(message)s')
    config_path = args.config.resolve()
    options = load_yaml(str(config_path)).get('kol_intent', {})

    def configured_path(key: str) -> Path:
        value = options.get(key)
        if not value:
            raise ValueError(f'Configure kol_intent.{key}')
        path = Path(value)
        return path if path.is_absolute() else config_path.parent / path

    posts = pd.read_csv(configured_path('posts_path'), dtype={'ticker': str})
    if options.get('prices_path'):
        prices = pd.read_csv(configured_path('prices_path'), dtype={'ticker': str})
    else:
        prices = load_public_prices(options.get('tickers', []), options.get('price_count', 250), options.get('adjustment', 'qfq'))
    result = analyze(posts, prices, options)
    export_report(result, configured_path('output_dir'))
    logging.getLogger(__name__).info('KOL research exported to %s', configured_path('output_dir'))


if __name__ == '__main__':
    main()
