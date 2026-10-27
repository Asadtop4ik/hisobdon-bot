from datetime import datetime
from zoneinfo import ZoneInfo
from hisobdon.db import Store
from hisobdon.ledger import Ledger
from hisobdon.conversation import Engine

NOW = datetime(2026,10,27,14,0,tzinfo=ZoneInfo('Asia/Tashkent'))

def pick(engine,replies,label):
    options = [(text, data) for reply in replies for row in reply.rows for text,data in row]
    callback = next(data for text,data in options if label in text)
    return engine.callback(callback, NOW), callback

def test_expense_with_account_button_and_duplicate(tmp_path):
    s=Store(tmp_path/'db')
    a=Ledger(s).create_account('Humo','UZS',10000000,'2026-10-01','card')
    engine=Engine(s)
    replies=engine.message('bugun ovqat abetga 40ming so‘m',1,NOW)
    replies, callback=pick(engine,replies,'Humo')
    assert 'Saqlandi' in replies[0].text
    assert Ledger(s).balance(a)==6000000
    engine.callback(callback,NOW)
    assert Ledger(s).balance(a)==6000000
    replies, _=pick(engine,replies,'Bekor qilish')
    replies,_=pick(engine,replies,'Ha, bekor')
    assert Ledger(s).balance(a)==10000000

def test_account_creation_survives_restart(tmp_path):
    path=tmp_path/'db'
    s=Store(path); e=Engine(s)
    replies=e.message('/accounts',1,NOW)
    replies,_=pick(e,replies,'Hisob qo‘shish')
    replies,_=pick(e,replies,'Naqd')
    replies=e.message('Hamyon',2,NOW)
    replies,_=pick(e,replies,'USD')
    s.close(); s=Store(path);e=Engine(s)
    replies=e.message('100',3,NOW)
    replies,_=pick(e,replies,'Bugun')
    replies,_=pick(e,replies,'Saqlash')
    assert Ledger(s).balances()[0]['balance']==10000
    assert Ledger(s).balances()[0]['currency']=='USD'

def test_unknown_input_requires_type_and_category(tmp_path):
    s=Store(tmp_path/'db');e=Engine(s)
    Ledger(s).create_account('Naqd','UZS',10000000,'2026-10-01')
    replies=e.message('40000',1,NOW)
    replies,_=pick(e,replies,'Chiqim')
    replies,_=pick(e,replies,'Ovqat')
    replies,_=pick(e,replies,'Naqd')
    assert Ledger(s).balances()[0]['balance']==6000000
