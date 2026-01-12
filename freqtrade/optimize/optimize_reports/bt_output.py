import logging
from typing import Any, Literal

from freqtrade.constants import UNLIMITED_STAKE_AMOUNT, Config
from freqtrade.ft_types import BacktestResultType
from freqtrade.optimize.optimize_reports.optimize_reports import generate_periodic_breakdown_stats
from freqtrade.util import decimals_per_coin, fmt_coin, print_rich_table


logger = logging.getLogger(__name__)


def _get_line_floatfmt(stake_currency: str) -> list[str]:
    """
    Generate floatformat (goes in line with _generate_result_line())
    """
    return ["s", "d", ".2f", f".{decimals_per_coin(stake_currency)}f", ".2f", "d", "s", "s"]


def _get_line_header(
    first_column: str | list[str], stake_currency: str, direction: str = "Trades"
) -> list[str]:
    """
    Generate header lines (goes in line with _generate_result_line())
    """
    return [
        *([first_column] if isinstance(first_column, str) else first_column),
        direction,
        "평균 수익률 %",
        f"총 수익 {stake_currency}",
        "총 수익률 %",
        "평균 보유시간",
        "승  무  패  승률%",
    ]


def generate_wins_draws_losses(wins, draws, losses):
    if wins > 0 and losses == 0:
        wl_ratio = "100"
    elif wins == 0:
        wl_ratio = "0"
    else:
        wl_ratio = f"{100.0 / (wins + draws + losses) * wins:.1f}" if losses > 0 else "100"
    return f"{wins:>4}  {draws:>4}  {losses:>4}  {wl_ratio:>4}"


def text_table_bt_results(
    pair_results: list[dict[str, Any]], stake_currency: str, title: str
) -> None:
    """
    Generates and returns a text table for the given backtest data and the results dataframe
    :param pair_results: List of Dictionaries - one entry per pair + final TOTAL row
    :param stake_currency: stake-currency - used to correctly name headers
    :param title: Title of the table
    """

    headers = _get_line_header("코인", stake_currency, "거래수")
    output = [
        [
            t["key"],
            t["trades"],
            t["profit_mean_pct"],
            f"{t['profit_total_abs']:.{decimals_per_coin(stake_currency)}f}",
            t["profit_total_pct"],
            t["duration_avg"],
            generate_wins_draws_losses(t["wins"], t["draws"], t["losses"]),
        ]
        for t in pair_results
    ]
    # Ignore type as floatfmt does allow tuples but mypy does not know that
    print_rich_table(output, headers, summary=title)


def text_table_tags(
    tag_type: Literal["enter_tag", "exit_tag", "mix_tag"],
    tag_results: list[dict[str, Any]],
    stake_currency: str,
) -> None:
    """
    Generates and returns a text table for the given backtest data and the results dataframe
    :param pair_results: List of Dictionaries - one entry per pair + final TOTAL row
    :param stake_currency: stake-currency - used to correctly name headers
    """
    floatfmt = _get_line_floatfmt(stake_currency)
    fallback: str = ""
    is_list = False
    if tag_type == "enter_tag":
        title = "진입 태그"
        headers = _get_line_header(title, stake_currency, "진입")
    elif tag_type == "exit_tag":
        title = "종료 사유"
        headers = _get_line_header(title, stake_currency, "종료")
        fallback = "exit_reason"
    else:
        # Mix tag
        title = "복합 태그"
        headers = _get_line_header(["진입 태그", "종료 사유"], stake_currency, "거래수")
        floatfmt.insert(0, "s")
        is_list = True

    output = [
        [
            *(
                (
                    list(t["key"])
                    if isinstance(t["key"], list | tuple)
                    else [t["key"], ""]
                    if is_list
                    else [t["key"]]
                )
                if t.get("key") is not None and len(str(t["key"])) > 0
                else [t.get(fallback, "OTHER")]
            ),
            t["trades"],
            t["profit_mean_pct"],
            f"{t['profit_total_abs']:.{decimals_per_coin(stake_currency)}f}",
            t["profit_total_pct"],
            t.get("duration_avg"),
            generate_wins_draws_losses(t["wins"], t["draws"], t["losses"]),
        ]
        for t in tag_results
    ]
    # Ignore type as floatfmt does allow tuples but mypy does not know that
    print_rich_table(output, headers, summary=f"{title.upper()} 통계")


def text_table_periodic_breakdown(
    days_breakdown_stats: list[dict[str, Any]], stake_currency: str, period: str
) -> None:
    """
    Generate small table with Backtest results by days
    :param days_breakdown_stats: Days breakdown metrics
    :param stake_currency: Stakecurrency used
    """
    headers = [
        period.capitalize(),
        "거래수",
        f"총 수익 {stake_currency}",
        "수익 팩터",
        "승  무  패  승률%",
    ]
    output = [
        [
            d["date"],
            d.get("trades", "N/A"),
            fmt_coin(d["profit_abs"], stake_currency, False),
            round(d["profit_factor"], 2) if "profit_factor" in d else "N/A",
            generate_wins_draws_losses(d["wins"], d["draws"], d.get("losses", d.get("loses", 0))),
        ]
        for d in days_breakdown_stats
    ]
    print_rich_table(output, headers, summary=f"{period.upper()}별 상세내역")


def text_table_strategy(strategy_results, stake_currency: str, title: str):
    """
    Generate summary table per strategy
    :param strategy_results: Dict of <Strategyname: DataFrame> containing results for all strategies
    :param stake_currency: stake-currency - used to correctly name headers
    """
    headers = _get_line_header("전략", stake_currency, "거래수")
    # _get_line_header() is also used for per-pair summary. Per-pair drawdown is mostly useless
    # therefore we slip this column in only for strategy summary here.
    headers.append("최대 낙폭")

    # Align drawdown string on the center two space separator.
    if "max_drawdown_account" in strategy_results[0]:
        drawdown = [f"{t['max_drawdown_account'] * 100:.2f}" for t in strategy_results]
    else:
        # Support for prior backtest results
        drawdown = [f"{t['max_drawdown_per']:.2f}" for t in strategy_results]

    dd_pad_abs = max([len(t["max_drawdown_abs"]) for t in strategy_results])
    dd_pad_per = max([len(dd) for dd in drawdown])
    drawdown = [
        f"{t['max_drawdown_abs']:>{dd_pad_abs}} {stake_currency}  {dd:>{dd_pad_per}}%"
        for t, dd in zip(strategy_results, drawdown, strict=False)
    ]

    output = [
        [
            t["key"],
            t["trades"],
            f"{t['profit_mean_pct']:.2f}",
            f"{t['profit_total_abs']:.{decimals_per_coin(stake_currency)}f}",
            t["profit_total_pct"],
            t["duration_avg"],
            generate_wins_draws_losses(t["wins"], t["draws"], t["losses"]),
            drawdown,
        ]
        for t, drawdown in zip(strategy_results, drawdown, strict=False)
    ]
    print_rich_table(output, headers, summary=title)


def text_table_add_metrics(strat_results: dict) -> None:
    stake = strat_results["stake_currency"]
    if len(strat_results["trades"]) > 0:
        best_trade = max(strat_results["trades"], key=lambda x: x["profit_ratio"])
        worst_trade = min(strat_results["trades"], key=lambda x: x["profit_ratio"])

        short_metrics = (
            [
                ("", ""),  # Empty line to improve readability
                (
                    "롱 / 숏 거래수",
                    f"{strat_results.get('trade_count_long', 'total_trades')} / "
                    f"{strat_results.get('trade_count_short', 0)}",
                ),
                (
                    "롱 / 숏 수익률 %",
                    f"{strat_results['profit_total_long']:.2%} / "
                    f"{strat_results['profit_total_short']:.2%}",
                ),
                (
                    f"롱 / 숏 수익금 {stake}",
                    f"{strat_results['profit_total_long_abs']:.{decimals_per_coin(stake)}f} / "
                    f"{strat_results['profit_total_short_abs']:.{decimals_per_coin(stake)}f}",
                ),
            ]
            if strat_results.get("trade_count_short", 0) > 0
            else []
        )

        drawdown_metrics = []
        if "max_relative_drawdown" in strat_results:
            # Compatibility to show old hyperopt results
            drawdown_metrics.append(
                ("최대 자산 하락폭(Underwater) %", f"{strat_results['max_relative_drawdown']:.2%}")
            )
        drawdown_account = (
            strat_results["max_drawdown_account"]
            if "max_drawdown_account" in strat_results
            else strat_results["max_drawdown"]
        )
        drawdown_metrics.extend(
            [
                (
                    "절대 낙폭(Drawdown)",
                    f"{fmt_coin(strat_results['max_drawdown_abs'], stake)} "
                    f"({drawdown_account:.2%})",
                ),
                (
                    "낙폭 지속 기간",
                    strat_results["drawdown_duration"]
                    if "drawdown_duration" in strat_results
                    else "N/A",
                ),
                (
                    "낙폭 시작 시점 수익금",
                    fmt_coin(strat_results["max_drawdown_high"], stake),
                ),
                (
                    "낙폭 종료 시점 수익금",
                    fmt_coin(strat_results["max_drawdown_low"], stake),
                ),
                ("낙폭 시작일", strat_results["drawdown_start"]),
                ("낙폭 종료일", strat_results["drawdown_end"]),
            ]
        )

        entry_adjustment_metrics = (
            [
                ("취소된 진입 거래", strat_results.get("canceled_trade_entries", "N/A")),
                ("취소된 진입 주문", strat_results.get("canceled_entry_orders", "N/A")),
                ("교체된 진입 주문", strat_results.get("replaced_entry_orders", "N/A")),
            ]
            if strat_results.get("canceled_entry_orders", 0) > 0
            else []
        )

        trading_mode = (
            (
                [
                    (
                        "거래 모드",
                        (
                            ""
                            if not strat_results.get("margin_mode")
                            or strat_results.get("trading_mode", "spot") == "spot"
                            else f"{strat_results['margin_mode'].capitalize()} "
                        )
                        + f"{strat_results['trading_mode'].capitalize()}",
                    )
                ]
            )
            if "trading_mode" in strat_results
            else []
        )

        # Newly added fields should be ignored if they are missing in strat_results. hyperopt-show
        # command stores these results and newer version of freqtrade must be able to handle old
        # results with missing new fields.
        metrics = [
            ("백테스팅 시작일", strat_results["backtest_start"]),
            ("백테스팅 종료일", strat_results["backtest_end"]),
            *trading_mode,
            ("최대 동시 거래수", strat_results["max_open_trades"]),
            ("", ""),  # Empty line to improve readability
            (
                "총 거래수 / 일평균",
                f"{strat_results['total_trades']} / {strat_results['trades_per_day']}",
            ),
            (
                "시작 자산",
                fmt_coin(strat_results["starting_balance"], stake),
            ),
            (
                "종료 자산",
                fmt_coin(strat_results["final_balance"], stake),
            ),
            (
                "순수익금 ",
                fmt_coin(strat_results["profit_total_abs"], stake),
            ),
            ("총 수익률 %", f"{strat_results['profit_total']:.2%}"),
            ("연평균 성장률(CAGR) %", f"{strat_results['cagr']:.2%}" if "cagr" in strat_results else "N/A"),
            ("Sortino", f"{strat_results['sortino']:.2f}" if "sortino" in strat_results else "N/A"),
            ("Sharpe", f"{strat_results['sharpe']:.2f}" if "sharpe" in strat_results else "N/A"),
            ("Calmar", f"{strat_results['calmar']:.2f}" if "calmar" in strat_results else "N/A"),
            ("SQN", f"{strat_results['sqn']:.2f}" if "sqn" in strat_results else "N/A"),
            (
                "수익 팩터",
                (
                    f"{strat_results['profit_factor']:.2f}"
                    if "profit_factor" in strat_results
                    else "N/A"
                ),
            ),
            (
                "기대 수익값 (비율)",
                (
                    f"{strat_results['expectancy']:.2f} ({strat_results['expectancy_ratio']:.2f})"
                    if "expectancy_ratio" in strat_results
                    else "N/A"
                ),
            ),
            (
                "일평균 수익금",
                fmt_coin(
                    (strat_results["profit_total_abs"] / strat_results["backtest_days"]),
                    stake,
                ),
            ),
            (
                "평균 진입 금액",
                fmt_coin(strat_results["avg_stake_amount"], stake),
            ),
            (
                "총 거래 대금",
                fmt_coin(strat_results["total_volume"], stake),
            ),
            *short_metrics,
            ("", ""),  # Empty line to improve readability
            (
                "최고 수익 코인",
                f"{strat_results['best_pair']['key']} "
                f"{strat_results['best_pair']['profit_total']:.2%}",
            ),
            (
                "최저 수익 코인",
                f"{strat_results['worst_pair']['key']} "
                f"{strat_results['worst_pair']['profit_total']:.2%}",
            ),
            ("최고 수익 거래", f"{best_trade['pair']} {best_trade['profit_ratio']:.2%}"),
            ("최악(최저) 수익 거래", f"{worst_trade['pair']} {worst_trade['profit_ratio']:.2%}"),
            (
                "최고 수익의 날",
                fmt_coin(strat_results["backtest_best_day_abs"], stake),
            ),
            (
                "최저 수익의 날",
                fmt_coin(strat_results["backtest_worst_day_abs"], stake),
            ),
            (
                "일별 승/무/패",
                f"{strat_results['winning_days']} / "
                f"{strat_results['draw_days']} / {strat_results['losing_days']}",
            ),
            (
                "승리 거래 보유시간 (최소/최대/평균)",
                f"{strat_results.get('winner_holding_min', 'N/A')} / "
                f"{strat_results.get('winner_holding_max', 'N/A')} / "
                f"{strat_results.get('winner_holding_avg', 'N/A')}",
            ),
            (
                "손실 거래 보유시간 (최소/최대/평균)",
                f"{strat_results.get('loser_holding_min', 'N/A')} / "
                f"{strat_results.get('loser_holding_max', 'N/A')} / "
                f"{strat_results.get('loser_holding_avg', 'N/A')}",
            ),
            (
                "최대 연속 승리 / 패배",
                (
                    (
                        f"{strat_results['max_consecutive_wins']} / "
                        f"{strat_results['max_consecutive_losses']}"
                    )
                    if "max_consecutive_losses" in strat_results
                    else "N/A"
                ),
            ),
            ("거부된 진입 신호", strat_results.get("rejected_signals", "N/A")),
            (
                "진입/종료 타임아웃",
                f"{strat_results.get('timedout_entry_orders', 'N/A')} / "
                f"{strat_results.get('timedout_exit_orders', 'N/A')}",
            ),
            *entry_adjustment_metrics,
            ("", ""),  # Empty line to improve readability
            ("최소 자산", fmt_coin(strat_results["csum_min"], stake)),
            ("최대 자산", fmt_coin(strat_results["csum_max"], stake)),
            *drawdown_metrics,
            ("시장 변화율", f"{strat_results['market_change']:.2%}"),
        ]
        print_rich_table(metrics, ["지표", "값"], summary="요약 지표", justify="left")

    else:
        start_balance = fmt_coin(strat_results["starting_balance"], stake)
        stake_amount = (
            fmt_coin(strat_results["stake_amount"], stake)
            if strat_results["stake_amount"] != UNLIMITED_STAKE_AMOUNT
            else "unlimited"
        )

        message = (
            "거래 내역이 없습니다. "
            f"시작 자산은 {start_balance}, "
            f"진입 금액은 {stake_amount} 였습니다."
        )
        print(message)


def _show_tag_subresults(results: dict[str, Any], stake_currency: str):
    """
    Print tag subresults (enter_tag, exit_reason_summary, mix_tag_stats)
    """
    if (enter_tags := results.get("results_per_enter_tag")) is not None:
        text_table_tags("enter_tag", enter_tags, stake_currency)

    if (exit_reasons := results.get("exit_reason_summary")) is not None:
        text_table_tags("exit_tag", exit_reasons, stake_currency)

    if (mix_tag := results.get("mix_tag_stats")) is not None:
        text_table_tags("mix_tag", mix_tag, stake_currency)


def show_backtest_result(
    strategy: str, results: dict[str, Any], stake_currency: str, backtest_breakdown: list[str]
):
    """
    Print results for one strategy
    """
    # Print results
    print(f"전략 결과: {strategy}")
    text_table_bt_results(
        results["results_per_pair"], stake_currency=stake_currency, title="백테스팅 결과"
    )
    text_table_bt_results(
        results["left_open_trades"], stake_currency=stake_currency, title="미체결(보유중) 거래 결과"
    )

    _show_tag_subresults(results, stake_currency)

    for period in backtest_breakdown:
        if period in results.get("periodic_breakdown", {}):
            days_breakdown_stats = results["periodic_breakdown"][period]
        else:
            days_breakdown_stats = generate_periodic_breakdown_stats(
                trade_list=results["trades"], period=period
            )
        text_table_periodic_breakdown(
            days_breakdown_stats=days_breakdown_stats, stake_currency=stake_currency, period=period
        )

    text_table_add_metrics(results)

    print()


def show_backtest_results(config: Config, backtest_stats: BacktestResultType):
    stake_currency = config["stake_currency"]

    for strategy, results in backtest_stats["strategy"].items():
        show_backtest_result(
            strategy, results, stake_currency, config.get("backtest_breakdown", [])
        )

    if len(backtest_stats["strategy"]) > 0:
        # Print Strategy summary table

        print(
            f"백테스팅 기간: {results['backtest_start']} -> {results['backtest_end']} |"
            f" 최대 동시 거래수 : {results['max_open_trades']}"
        )
        text_table_strategy(
            backtest_stats["strategy_comparison"], stake_currency, "전략 요약"
        )


def show_sorted_pairlist(config: Config, backtest_stats: BacktestResultType):
    if config.get("backtest_show_pair_list", False):
        for strategy, results in backtest_stats["strategy"].items():
            print(f"Pairs for Strategy {strategy}: \n[")
            for result in results["results_per_pair"]:
                if result["key"] != "TOTAL":
                    print(f'"{result["key"]}",  // {result["profit_mean"]:.2%}')
            print("]")
