# coding: utf-8
"""Explicit directional intent plus a separate sentiment-only comparator."""

import hashlib
import logging
import re

import numpy as np
import pandas as pd

from curs.kol_intent.data import local_timestamp, ticker_code

logger = logging.getLogger(__name__)
EVENT_COLUMNS = ['event_id', 'timestamp', 'ticker', 'direction', 'confidence',
                 'text_embedding', 'text', 'evidence', 'backend', 'supported_long']
LONG = r'\b(?:buy|long|bullish)\b|看多|买入|加仓'
SHORT = r'\b(?:sell|short|bearish)\b|看空|卖出|减仓'


def rule_direction(text: str) -> tuple[str, list[str]]:
    """Require explicit, unambiguous, unnegated directional keywords."""
    # Negated and conflicting statements are deliberately conservative.
    if re.search(r"\b(?:not|never|don't|do not|won't)\s+(?:\w+\s+){0,2}(?:buy|long|bullish|sell|short|bearish)\b|(?:不|别|不要|并非)(?:再|建议)?(?:看多|买入|加仓|看空|卖出|减仓)", text, re.I):
        return 'neutral', []
    positive, negative = re.findall(LONG, text, re.I), re.findall(SHORT, text, re.I)
    if bool(positive) == bool(negative):
        return 'neutral', positive + negative
    return ('long', positive) if positive else ('short', negative)


def fallback_embedding(text: str) -> list[float]:
    """Provide a stable normalized 64-dimensional token hash embedding."""
    vector = np.zeros(64)
    for token in re.findall(r'[a-z0-9]+|[\u4e00-\u9fff]', text.lower()):
        digest = hashlib.sha256(token.encode('utf-8')).digest()
        vector[int.from_bytes(digest[:2], 'big') % 64] += 1 if digest[2] % 2 else -1
    norm = np.linalg.norm(vector)
    return (vector / norm if norm else vector).tolist()


class IntentExtractor:
    """Lazily load FinBERT; model/import/inference failure falls back to rules."""

    def __init__(self, use_finbert: bool = True, model_name: str = 'ProsusAI/finbert',
                 local_files_only: bool = True) -> None:
        self.backend = 'keywords'
        self.tokenizer = self.model = self.torch = None
        if use_finbert:
            try:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=local_files_only)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_name, local_files_only=local_files_only)
                self.model.eval()
                self.torch = torch
                self.backend = 'finbert'
            except Exception:
                logger.warning('FinBERT unavailable; continuing with keyword rules', exc_info=True)

    def features(self, text: str) -> tuple[str, float, list[float]]:
        """Return sentiment, its probability, and pooled model or hash features."""
        if self.model is not None:
            try:
                inputs = self.tokenizer(text, return_tensors='pt', truncation=True, max_length=512)
                with self.torch.no_grad():
                    output = self.model(**inputs, output_hidden_states=True)
                probabilities = output.logits.softmax(dim=-1)[0]
                index = int(probabilities.argmax())
                label = self.model.config.id2label[index].lower()
                direction = {'positive': 'long', 'negative': 'short', 'neutral': 'neutral'}[label]
                mask = inputs['attention_mask'].unsqueeze(-1)
                pooled = (output.hidden_states[-1] * mask).sum(dim=1) / mask.sum(dim=1)
                return direction, float(probabilities[index]), pooled[0].tolist()
            except Exception:
                logger.warning('FinBERT inference failed; continuing with keyword rules', exc_info=True)
                self.model = None
                self.backend = 'keywords'
        positive = bool(re.search(LONG + r'|\b(?:good|great|profit|optimistic)\b|利好|盈利|乐观', text, re.I))
        negative = bool(re.search(SHORT + r'|\b(?:bad|loss|pessimistic)\b|利空|亏损|悲观', text, re.I))
        direction = 'neutral' if positive == negative else 'long' if positive else 'short'
        return direction, 0.5 if direction == 'neutral' else 0.75, fallback_embedding(text)

    def extract(self, posts: pd.DataFrame, tickers: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Return intent and sentiment events; never infer ticker-less mentions."""
        if not {'timestamp', 'ticker', 'text'}.issubset(posts.columns):
            raise ValueError('Posts require timestamp, ticker, text')
        valid = {ticker_code(ticker) for ticker in tickers}
        intents, sentiments = [], []
        for number, post in enumerate(posts.to_dict('records')):
            ticker = ticker_code(post['ticker'])
            if ticker not in valid:
                continue
            stamp = local_timestamp(post['timestamp'])
            text = '' if pd.isna(post['text']) else str(post['text'])
            direction, evidence = rule_direction(text)
            sentiment, probability, embedding = self.features(text)
            row = dict(event_id=f'post_{number}', timestamp=stamp, ticker=ticker,
                       direction=direction, confidence=probability if sentiment == direction else 0.75,
                       text_embedding=embedding, text=text, evidence=evidence,
                       backend=self.backend, supported_long=direction == 'long')
            if direction != 'neutral':
                intents.append(row)
            if sentiment != 'neutral':
                sentiments.append(dict(row, direction=sentiment, confidence=probability))
        return (pd.DataFrame(intents, columns=EVENT_COLUMNS),
                pd.DataFrame(sentiments, columns=EVENT_COLUMNS))
