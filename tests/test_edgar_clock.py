"""SEC acceptance time comes from the index header, converted in America/New_York."""

from datetime import datetime, timedelta, timezone

from aftermath_api.sources.edgar import acceptance_clock, parse_acceptance_header, select_filings


def _payload(cik, accession, json_time, item="2.02"):
    return {
        "cik": cik,
        "filings": {"recent": {
            "form": ["8-K"],
            "items": [item],
            "acceptanceDateTime": [json_time],
            "accessionNumber": [accession],
            "primaryDocument": ["results.htm"],
        }},
    }


def _select(cik, accession, json_time, header, now):
    return select_filings(
        "NVDAUSDT",
        _payload(cik, accession, json_time),
        now.isoformat(),
        now=now,
        index_lookup=lambda _cik, _accession: header,
    )


def test_shifted_nvda_and_meta_use_the_index_header_not_the_json_instant():
    nvda = _select(
        "1045810",
        "0001045810-26-000073",
        "2026-08-27T00:21:19.000Z",
        "<ACCEPTANCE-DATETIME>20260826162119",
        datetime(2026, 8, 26, 20, 30, tzinfo=timezone.utc),
    )
    assert nvda[0]["event_time_utc"].startswith("2026-08-26T20:21:19")
    assert nvda[0]["payload"]["clock_source"] == "sec_index_header"
    assert nvda[0]["payload"]["json_minus_index_s"] == 4 * 3600
    meta = _select(
        "1326801",
        "0001628280-26-050596",
        "2026-07-30T00:03:23.000Z",
        "ACCEPTANCE-DATETIME: 20260729160323",
        datetime(2026, 7, 29, 20, 10, tzinfo=timezone.utc),
    )
    assert meta[0]["event_time_utc"].startswith("2026-07-29T20:03:23")
    assert meta[0]["payload"]["json_minus_index_s"] == 4 * 3600


def test_an_already_correct_issuer_is_not_shifted():
    rows = _select(
        "1652044",
        "0001652044-26-000066",
        "2026-07-22T20:01:36.000Z",
        "<ACCEPTANCE-DATETIME>20260722160136",
        datetime(2026, 7, 22, 20, 10, tzinfo=timezone.utc),
    )
    assert rows[0]["event_time_utc"].startswith("2026-07-22T20:01:36")
    assert rows[0]["payload"]["json_minus_index_s"] == 0


def test_an_est_month_header_is_five_hours_from_utc():
    instant = parse_acceptance_header("<ACCEPTANCE-DATETIME>20260115160000")
    assert instant == datetime(2026, 1, 15, 21, 0, tzinfo=timezone.utc)
    rows = _select(
        "1318605",
        "0001318605-26-000001",
        "2026-01-15T21:00:00.000Z",
        "<ACCEPTANCE-DATETIME>20260115160000",
        datetime(2026, 1, 15, 21, 5, tzinfo=timezone.utc),
    )
    assert rows[0]["event_time_utc"].startswith("2026-01-15T21:00:00")
    assert rows[0]["payload"]["json_minus_index_s"] == 0


def test_a_missing_header_is_not_replaced_with_the_json_time():
    now = datetime(2026, 8, 26, 20, 30, tzinfo=timezone.utc)
    rows = _select("1045810", "0001045810-26-000073", "2026-08-26T20:21:19.000Z", "", now)
    assert rows == []
    clock = acceptance_clock("", datetime(2026, 8, 26, 20, 21, 19, tzinfo=timezone.utc))
    assert clock["clock_source"] == "acceptance_time_unverified"
    assert clock["accepted_at_utc"] is None


def test_a_correct_json_row_is_not_moved_by_a_fixed_offset():
    """TSLA-like: the JSON instant already matches the header, so it stays put."""
    now = datetime(2026, 10, 2, 13, 10, tzinfo=timezone.utc)
    header = "<ACCEPTANCE-DATETIME>20261002090426"
    parsed = parse_acceptance_header(header)
    assert parsed is not None
    json_time = parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    rows = _select("1318605", "0001318605-26-000090", json_time, header, now)
    assert rows[0]["payload"]["json_minus_index_s"] == 0
    assert rows[0]["event_time_utc"].startswith(parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))
    shifted = (parsed - timedelta(hours=4)).isoformat()
    assert not rows[0]["event_time_utc"].startswith(shifted[:19])
