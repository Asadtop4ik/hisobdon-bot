from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from hisobdon.parser import parse

NOW = datetime(2026,10,27,14,0,tzinfo=ZoneInfo('Asia/Tashkent'))

@pytest.mark.parametrize('text,amount', [('bugun ovqat abetga 40ming so‘m',4000000), ('40 000 tushlik',4000000), ('taksi 40k',4000000), ('oylik 1,5 mln',150000000), ('$12.50 sovg‘a',1250)])
def test_amounts(text,amount):
    assert parse(text,NOW)['amount'] == amount

def test_categories_and_relative_dates():
    d = parse('kecha ovqat 40 ming so‘m', NOW)
    assert (d['date'],d['kind'],d['category'],d['currency']) == ('2026-10-26','expense','Ovqat','UZS')

def test_multiple_amounts_are_not_silently_added():
    d = parse('ovqat 40ming taksi 20ming',NOW)
    assert d.get('amount') is None
    assert d.get('error')

def test_iso_date_is_not_an_amount():
    d = parse('2026-10-25 ovqat 40000',NOW)
    assert (d['date'], d['amount']) == ('2026-10-25',4000000)

def test_unsupported_currency_is_not_assumed_uzs():
    assert parse('50 eur ovqat',NOW).get('error')
