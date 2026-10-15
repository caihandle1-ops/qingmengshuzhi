"""Expanded catalog queries keep explicit annual scope and read-only execution."""
from datetime import date
import sqlite3

import pytest

from core import db, qa_engine
from core.analysis import rows_to_df
from core.builtin_catalog import get_builtin_companies
from core.company_identity import explicit_company_names
from core.conversation import new_conversation_context, resolve_turn
from core.qa_engine import answer_question, parse_question
from core.seed import seed_sample_data
from core.storage import workspace_context
from core.text_to_sql import execute_readonly_sql, generate_sql, get_readonly_connection, validate_sql


YEARS = [2021, 2022, 2023, 2024, 2025]


class ReviewDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 14)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(qa_engine, 'date', ReviewDate)


@pytest.fixture(scope='module')
def annual_library(tmp_path_factory):
    with workspace_context('evaluation', tmp_path_factory.mktemp('annual_queries'), allow_writes=True):
        db.init_db(migrate_legacy=False)
        seed_sample_data()
        companies = db.fetch_companies()
        data = {row['name']: rows_to_df(db.fetch_company_metrics(row['id'])) for row in companies}
        assert len(data) == 50
        yield data


@pytest.mark.parametrize('reference', ['alias', 'stock_code'])
def test_all_fifty_companies_query_by_short_name_or_ticker(annual_library, reference):
    names = list(annual_library)
    for company in get_builtin_companies():
        token = company['aliases'][0] if reference == 'alias' else company[reference]
        question = token + '近五年营业收入趋势'
        result = answer_question(question, names[0], None, names, annual_library)
        assert result['status'] == 'success', (token, result.get('reason'))
        assert result['parsed']['companies'] == [company['name']], token
        assert result['parsed']['years'] == YEARS, token
        assert result['sql_result']['status'] == 'success', token
        assert result['sql_result']['row_count'] == 5, token
        assert {row['year'] for row in result['sql_result']['rows']} == set(YEARS)
        assert {row['company'] for row in result['sql_result']['rows']} == {company['name']}
        assert result['chart'] == 'trend'
        assert all(f'{year}年' in result['answer'] for year in YEARS)


@pytest.mark.parametrize('phrase', ['近五年', '近5年', '最近五个完整年度', '最近5个完整年度', '过去五年'])
def test_recent_five_years_override_page_and_history(annual_library, phrase):
    names = list(annual_library)
    target = get_builtin_companies()[3]
    context = {**new_conversation_context(), 'primary_company': names[0],
               'years': [2023], 'metrics': ['net_profit'], 'intent': 'finance_query'}
    question = target['aliases'][0] + phrase + '营收趋势'
    turn = resolve_turn(context, question, names, page_company=names[0], page_year=2024)
    assert turn['status'] == 'ready'
    assert turn['resolved']['companies'] == [target['name']]
    assert turn['resolved']['years'] == YEARS
    assert turn['resolved']['explicit_scope']['years'] == YEARS
    assert turn['context']['years'] == YEARS
    # Even a stale or external resolved context cannot override this explicit scope.
    result = answer_question(question, names[0], None, names, annual_library,
                             resolved_context={**turn['resolved'], 'years': [2024]})
    assert result['parsed']['years'] == YEARS
    assert result['sql_result']['row_count'] == 5


def test_relative_followup_retains_company_but_replaces_previous_year(annual_library):
    names = list(annual_library)
    company = get_builtin_companies()[3]
    initial = resolve_turn(None, company['stock_code'] + ' 2024年营收', names,
                           page_company=names[0], page_year=2022)
    followup = resolve_turn(initial['context'], '那近五年呢', names,
                            page_company=names[0], page_year=2022)
    assert followup['status'] == 'ready'
    assert followup['resolved']['companies'] == [company['name']]
    assert followup['resolved']['years'] == YEARS
    assert followup['resolved']['metrics'] == ['revenue']
    result = answer_question('那近五年呢', names[0], None, names, annual_library,
                             resolved_context=followup['resolved'])
    assert result['status'] == 'success'
    assert result['sql_result']['row_count'] == 5


@pytest.mark.parametrize('span', ['2021—2025', '2021-2025', '2021至2025'])
def test_literal_five_year_range_is_not_limited_to_three(annual_library, span):
    names = list(annual_library)
    question = '上汽集团' + span + '年营收趋势'
    parsed = parse_question(question, names, names[0], '平衡型')
    assert parsed['years'] == YEARS
    assert 'LIMIT' not in generate_sql(parsed).sql
    result = answer_question(question, names[0], None, names, annual_library)
    assert result['sql_result']['row_count'] == 5


def test_unspecified_trend_retains_existing_three_year_default(annual_library):
    names = list(annual_library)
    parsed = parse_question('上汽集团营收趋势', names, names[0], '平衡型')
    assert parsed['years'] == []
    assert 'LIMIT 3' in generate_sql(parsed).sql
    result = answer_question('上汽集团营收趋势', names[0], None, names, annual_library)
    assert result['sql_result']['row_count'] == 3


def test_recent_five_years_excludes_current_year_and_does_not_fill_missing_data(annual_library):
    names = list(annual_library)
    target = get_builtin_companies()[3]['name']
    partial = dict(annual_library)
    partial[target] = annual_library[target].query('year > 2021')
    result = answer_question('上汽集团近五年营收趋势', names[0], None, names, partial)
    assert result['status'] == 'missing_scope'
    assert result['missing_scope'] == [{'company': target, 'year': 2021}]
    assert 2026 not in result['parsed']['years']


@pytest.mark.parametrize('unknown', ['未接入科技', '999999'])
def test_unknown_company_never_uses_selected_company(annual_library, unknown):
    names = list(annual_library)
    question = unknown + '近五年营收趋势'
    turn = resolve_turn(None, question, names, page_company=names[0], page_year=2024)
    if turn['status'] == 'needs_clarification':
        assert turn['field'] == 'company'
    else:
        assert names[0] not in turn['resolved']['companies']
    result = answer_question(question, names[0], None, names, annual_library,
                             resolved_context=turn.get('resolved'))
    assert result['status'] == 'unknown_company'
    assert result['sql_result']['status'] == 'not_applicable'


def test_catalog_does_not_grant_access_or_match_partial_tickers(annual_library):
    company = get_builtin_companies()[3]
    names = [name for name in annual_library if name != company['name']]
    assert explicit_company_names(company['aliases'][0], names) == []
    assert explicit_company_names(company['stock_code'], names) == []
    assert explicit_company_names('1' + company['stock_code'], list(annual_library)) == []
    assert explicit_company_names('X' + company['stock_code'], list(annual_library)) == []


def test_new_catalog_queries_keep_database_readonly(annual_library):
    before = db.get_db_path().read_bytes()
    parsed = parse_question('600104近五年营收趋势', list(annual_library), '', '平衡型')
    plan = generate_sql(parsed)
    assert validate_sql(plan.sql, plan.params)['valid']
    assert execute_readonly_sql(plan.sql, plan.params)['row_count'] == 5
    for sql in ['DELETE FROM companies;', 'SELECT * FROM companies; DROP TABLE companies;',
                'ATTACH DATABASE ? AS other;', 'PRAGMA writable_schema=ON;']:
        assert not validate_sql(sql, [])['valid']
    connection = get_readonly_connection()
    try:
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute('DELETE FROM companies')
    finally:
        connection.close()
    assert db.get_db_path().read_bytes() == before
