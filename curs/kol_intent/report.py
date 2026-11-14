# coding: utf-8
"""Research orchestration, explicit metric denominators and portable reports."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from curs.kol_intent.baseline import generate_trades
from curs.kol_intent.data import prepare_prices
from curs.kol_intent.event_study import event_study
from curs.kol_intent.extractor import IntentExtractor


def metrics(trades: pd.DataFrame, daily: pd.DataFrame, events: pd.DataFrame) -> dict:
    """Use 252 sessions, zero risk-free rate and an initial NAV of one."""
    returns = daily['daily_return'].to_numpy(dtype=float)
    equity = np.r_[1.0, np.cumprod(1.0 + returns)]
    deviation = returns.std(ddof=1) if len(returns) > 1 else 0.0
    reversals = pairs = 0
    for _, group in events.groupby('ticker'):
        directions = group.sort_values(['timestamp', 'event_id'])['direction'].tolist()
        pairs += max(0, len(directions) - 1)
        reversals += sum(a != b for a, b in zip(directions, directions[1:]))
    unsupported = int((~trades['supported_long'].astype(bool)).sum()) if len(trades) else 0
    return dict(cumulative_return=float(equity[-1] - 1),
                annualized_sharpe=float(np.sqrt(252) * returns.mean() / deviation) if deviation > 0 else None,
                max_drawdown=float((equity / np.maximum.accumulate(equity) - 1).min()),
                uer=unsupported / len(trades) if len(trades) else None,
                unsupported_entries=unsupported, entries=len(trades),
                drr=reversals / pairs if pairs else None, reversals=reversals, comparable_pairs=pairs)


def analyze(posts: pd.DataFrame, prices: pd.DataFrame, config: dict | None = None) -> dict:
    """Produce events, simulated trades, daily returns, CAR and both baselines."""
    options = config or {}
    prices = prepare_prices(prices)
    extractor = IntentExtractor(use_finbert=options.get('use_finbert', True),
                                model_name=options.get('model_name', 'ProsusAI/finbert'),
                                local_files_only=options.get('local_files_only', True))
    events, sentiment_events = extractor.extract(posts, set(prices['ticker']))
    trades, daily = generate_trades(events, prices, options.get('holding_days', 5))
    sentiment_trades, sentiment_daily = generate_trades(sentiment_events, prices, options.get('holding_days', 5))
    study, curve = event_study(events, prices)
    return dict(intent_events=events, trades=trades, daily_returns=daily, event_study=study,
                mean_car=curve, sentiment_events=sentiment_events, sentiment_trades=sentiment_trades,
                sentiment_daily_returns=sentiment_daily,
                report=dict(intent=metrics(trades, daily, events),
                            sentiment=metrics(sentiment_trades, sentiment_daily, sentiment_events),
                            backends=sorted(set(events['backend']) | set(sentiment_events['backend'])),
                            assumptions=['Simulated open fills; zero fees/slippage; no liquidity/limit checks.',
                                         'Equal weights at open; overnight gaps belong to prior holdings.',
                                         'Missing entry opens skip signals; missing exit opens defer exits.',
                                         'Missing valuations carry last close; open trades remain marked to market.',
                                         'Input prices must use a consistent adjustment and point-in-time universe.',
                                         'UER uses explicit keyword evidence, not human-labeled intent accuracy.',
                                         'FinBERT sentiment is separate from explicit directional intent; Chinese quality is not guaranteed.']))


def export_report(result: dict, output_dir: Path) -> None:
    """Export all tables, metrics, a static mean-CAR chart and Markdown report."""
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, table in result.items():
        if isinstance(table, pd.DataFrame):
            table = table.copy()
            for field in ('text_embedding', 'evidence'):
                if field in table:
                    table[field] = table[field].map(lambda value: json.dumps(value, ensure_ascii=False))
            table.to_csv(output_dir / f'{name}.csv', index=False, encoding='utf-8-sig')
    report = result['report']
    (output_dir / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    curve = result['mean_car']
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.plot(curve['relative_day'], curve['mean_car'], marker='o')
    axis.axvline(0, color='gray', linestyle='--')
    axis.axhline(0, color='gray', linewidth=0.5)
    axis.set(xlabel='Trading sessions relative to event', ylabel='Mean cumulative abnormal return', title='KOL intent: CAR [-1, +5]')
    figure.tight_layout()
    figure.savefig(output_dir / 'mean_car.png', dpi=150)
    plt.close(figure)
    lines = ['# KOL intent research', '', '| Metric | Intent | Sentiment only |', '|---|---:|---:|']
    for field in ('cumulative_return', 'annualized_sharpe', 'max_drawdown', 'uer', 'drr', 'entries'):
        lines.append(f"| {field} | {report['intent'][field]} | {report['sentiment'][field]} |")
    lines += ['', 'UER = unsupported entries / entries. DRR = reversals / adjacent non-neutral event pairs.',
              'CAR sums stock minus equal-weight market close returns; incomplete windows have null CAR.',
              'The mean curve reports available cumulative windows; see event_count in mean_car.csv.',
              '', '![Mean CAR](mean_car.png)', ''] + ['- ' + item for item in report['assumptions']]
    (output_dir / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
