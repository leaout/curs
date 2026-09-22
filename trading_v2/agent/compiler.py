# coding: utf-8
"""Compile natural-language strategy changes into an allowlisted schema."""

import json

from pydantic import ValidationError

from trading_v2.agent.models import CompilationResult, StrategySpec, strategy_json_schema
from trading_v2.agent.providers import ModelProvider, ModelProviderError


SYSTEM_PROMPT = """你是交易策略编译器，不是下单程序。
把用户的自然语言要求转换成严格 JSON，不生成 Python，不调用任何工具，也不承诺收益。
instrument 必须使用 asset_class:venue:symbol，例如 cn_equity:XSHG:600519。
只允许 Schema 中列出的指标和操作符。信息不足时采用保守默认值，并在 thesis 中说明。
输出必须是单个 JSON 对象，不要 Markdown。"""


class StrategyCompiler:
    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider

    async def compile(
        self,
        message: str,
        previous_strategy: dict | None = None,
    ) -> CompilationResult:
        context = ""
        if previous_strategy:
            context = f"\n当前策略 JSON：{json.dumps(previous_strategy, ensure_ascii=False)}"
        try:
            raw = await self.provider.complete_json(
                SYSTEM_PROMPT,
                f"用户要求：{message}{context}",
                strategy_json_schema(),
            )
            strategy = StrategySpec.model_validate(raw)
            return CompilationResult(
                assistant_content=(
                    f"已生成策略版本：{strategy.name}。周期 {strategy.timeframe}，"
                    f"包含 {len(strategy.entry_rules)} 个入场条件和 {len(strategy.exit_rules)} 个退出条件。"
                    "当前版本仅保存为草稿，发布后才会参与信号计算。"
                ),
                summary=f"{strategy.name} · {strategy.timeframe} · 仓位≤{strategy.risk.max_position_pct:%}",
                strategy=strategy,
                model_provider=self.provider.provider_name,
                model_name=self.provider.model_name,
            )
        except (ModelProviderError, ValidationError) as exc:
            compact = " ".join(message.split())
            summary = compact if len(compact) <= 48 else f"{compact[:48]}…"
            return CompilationResult(
                assistant_content=f"已保存你的修改，但暂未生成可运行策略：{exc}",
                summary=summary,
                warning=str(exc),
            )

    async def close(self) -> None:
        await self.provider.close()
