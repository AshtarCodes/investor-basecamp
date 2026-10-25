from datetime import UTC, date, datetime

from support import priced, request

from pricing_engine import project_dividends

VALUATION = date(2026, 10, 24)


def test_a_quarterly_payer_is_projected_every_three_months_through_the_expiry():
    # SPY's quote on 2026-10-24.
    projection = project_dividends(
        next_div_ex_date="2026-12-18T00:00:00Z",
        div_pay_amount=1.88883,
        div_freq=4,
        div_yield=0.97729,
        valuation_date=VALUATION,
        expiry=date(2027, 6, 30),
    )
    assert projection.rule == "quarterly-from-next-ex-date"
    assert [(d.ex_date, d.amount) for d in projection.dividends] == [
        (date(2026, 12, 18), 1.88883),
        (date(2027, 3, 18), 1.88883),
        (date(2027, 6, 18), 1.88883),
    ]


def project(
    *,
    next_div_ex_date: str | None = None,
    div_pay_amount: float = 0.0,
    div_freq: int = 0,
    div_yield: float = 0.0,
    valuation_date: date = VALUATION,
    expiry: date = date(2027, 6, 30),
):
    return project_dividends(
        next_div_ex_date=next_div_ex_date,
        div_pay_amount=div_pay_amount,
        div_freq=div_freq,
        div_yield=div_yield,
        valuation_date=valuation_date,
        expiry=expiry,
    )


def test_a_name_with_a_yield_but_no_frequency_needs_a_continuous_yield():
    # SATA's quote: pays daily, so Schwab reports divFreq 0 beside a 13% yield and a past ex-date.
    projection = project(
        next_div_ex_date="2026-10-22T00:00:00Z", div_pay_amount=0.05, div_yield=13.24694
    )
    assert projection.rule == "needs-continuous-yield"
    assert projection.dividends == ()


def test_a_name_with_every_dividend_field_zero_has_no_schedule():
    # IREN's quote.
    projection = project()
    assert projection.rule == "none"
    assert projection.dividends == ()


def test_a_next_ex_date_after_the_expiry_has_no_dividend_in_the_life():
    projection = project(
        next_div_ex_date="2026-12-18T00:00:00Z",
        div_pay_amount=1.88883,
        div_freq=4,
        div_yield=0.97729,
        expiry=date(2026, 12, 17),
    )
    assert projection.rule == "none-before-expiry"
    assert projection.dividends == ()


def test_an_ex_date_on_the_expiry_counts():
    projection = project(
        next_div_ex_date="2026-12-18T00:00:00Z",
        div_pay_amount=1.88883,
        div_freq=4,
        expiry=date(2026, 12, 18),
    )
    assert [d.ex_date for d in projection.dividends] == [date(2026, 12, 18)]


def test_other_frequencies_are_not_guessed():
    for freq in (1, 2, 12):
        projection = project(
            next_div_ex_date="2026-12-18T00:00:00Z", div_pay_amount=0.5, div_freq=freq
        )
        assert projection.rule == "unsupported-frequency"
        assert projection.dividends == ()


def test_a_quarterly_payer_without_a_next_ex_date_cannot_be_projected():
    projection = project(div_pay_amount=1.0, div_freq=4)
    assert projection.rule == "missing-ex-date"
    assert projection.dividends == ()


def test_a_stale_next_ex_date_rolls_forward_a_quarter_at_a_time():
    projection = project(
        next_div_ex_date="2026-04-30T00:00:00Z",
        div_pay_amount=0.5,
        div_freq=4,
        expiry=date(2027, 2, 1),
    )
    assert projection.rule == "quarterly-from-next-ex-date"
    assert projection.rolled_forward
    assert [d.ex_date for d in projection.dividends] == [date(2026, 10, 30), date(2027, 1, 30)]


def test_an_ex_date_today_is_kept_for_the_engine_to_judge_by_the_clock():
    projection = project(
        next_div_ex_date="2026-10-24T00:00:00Z",
        div_pay_amount=0.5,
        div_freq=4,
        expiry=date(2026, 12, 1),
    )
    assert not projection.rolled_forward
    assert [d.ex_date for d in projection.dividends] == [date(2026, 10, 24)]


def test_month_ends_clamp_without_drifting():
    projection = project(
        next_div_ex_date="2026-08-31T00:00:00Z",
        div_pay_amount=0.5,
        div_freq=4,
        valuation_date=date(2026, 8, 1),
        expiry=date(2027, 6, 30),
    )
    assert [d.ex_date for d in projection.dividends] == [
        date(2026, 8, 31),
        date(2026, 11, 30),
        date(2027, 2, 28),
        date(2027, 5, 31),
    ]


def test_a_projected_schedule_feeds_the_pricer_and_raises_an_american_put():
    # SPY's schedule through a 2027-06-30 expiry, priced as an 800 put on a spot of 700.
    schedule = project_dividends(
        next_div_ex_date="2026-12-18T00:00:00Z",
        div_pay_amount=1.88883,
        div_freq=4,
        div_yield=0.97729,
        valuation_date=VALUATION,
        expiry=date(2027, 6, 30),
    ).dividends
    option = {
        "right": "put",
        "exercise": "american",
        "strike": 800.0,
        "spot": 700.0,
        "sigma": 0.2,
        "expiry": date(2027, 6, 30),
        "valuation": datetime(2026, 10, 24, 20, 0, tzinfo=UTC),
    }
    assert priced(request(**option, dividends=schedule)) > priced(request(**option)) + 0.1
