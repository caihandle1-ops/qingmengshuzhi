"""No live APIs: verify distinct requests, evidence guards and native consent."""
from copy import deepcopy
import json

import pytest
from streamlit.testing.v1 import AppTest

from core import multi_agent_review as review
from core.execution_budget import current_budget
from core.llm import LLMRequestError


CONFIG = {'provider': 'DeepSeek', 'base_url': 'https://api.deepseek.com/v1',
          'model': 'deepseek-chat', 'api_key': 'test-placeholder-not-a-real-key'}


def entry():
    return {'question': '模拟公司2024年营业收入是多少？',
            'result': {'answer': '原始回答不得更改', 'delivery_state': {'status': 'pending', 'deliverable': False},
                'data_snapshot': {'模拟公司': [{'year': 2024, 'revenue': 100,
                    'api_key': 'must-never-send', 'internal_path': 'C:/private/data.csv',
                    'metric_provenance': {'revenue': {'file_name': '年度指标_模拟.csv',
                        'file_path': 'C:/private/data.csv', 'cell': 'B2', 'raw_value': '100', 'raw_unit': '亿元',
                        'snippet': '2024年营业收入为100亿元。'}}}]},
                'report_files_snapshot': [{'file_name': '整库不能外发.pdf', 'file_path': 'C:/private/library.pdf'}],
                'sql_result': {'sql': 'SELECT secret FROM credentials', 'rows': []}}}


def opinion(text='该事实可以定位到记录来源；仍需人工核对报表范围。', refs=None):
    return json.dumps({'notes': [{'text': text, 'evidence_ids': refs if refs is not None else ['E001']}]}, ensure_ascii=False)


def test_three_independent_roles_receive_validated_predecessors_and_preserve_answer():
    original = entry()
    before = deepcopy(original)
    calls = []
    def transport(config, messages, **kwargs):
        assert current_budget() is not None
        assert kwargs['temperature'] == 0 and 0 < kwargs['timeout'] <= 20 and kwargs['max_tokens'] <= 1000
        calls.append(deepcopy(messages))
        return opinion(['营业收入为100亿元，需要核对原始记录。', '应确认引用的报表范围与问题一致。', '请结合双方意见核对来源，保留待人工确认状态。'][len(calls) - 1])
    result = review.run_multi_agent_review(original, CONFIG, confirmed=True, transport=transport)
    assert result['status'] == 'opinions_ready'
    assert len(calls) == 3 and len({messages[0]['content'] for messages in calls}) == 3
    for index, messages in enumerate(calls):
        assert messages[0]['role'] == 'system'
        sent = json.loads(messages[1]['content'])
        assert sent['selected_answer_facts']['answer_excerpt'] == '原始回答不得更改'
        assert 'revision' not in sent['selected_answer_facts']
        previous = sent['previous_review_opinions']
        assert len(previous) == index
        assert [item['role'] for item in previous] == ['analyst', 'critic'][:index]
    assert [role['status'] for role in result['roles']] == ['reviewed'] * 3
    assert len(result['events']) == 9 and result['budget']['budget_seconds'] == 55
    assert result['model'] == {'provider': 'DeepSeek', 'model': 'deepseek-chat'}
    assert original == before and original['result']['delivery_state']['status'] == 'pending'


def test_packet_allowlist_strips_paths_credentials_full_sql_and_other_library():
    original = entry()
    original['question'] += ' 路径 C:/Users/private/account.csv api_key=must-be-redacted ' + CONFIG['api_key']
    original['result']['data_snapshot']['模拟公司'][0]['metric_provenance']['revenue']['snippet'] += ' https://secret.example/?token=x'
    packet = review.build_review_packet(original, secret_values=(CONFIG['api_key'],))
    text = json.dumps(packet, ensure_ascii=False)
    for forbidden in ('C:/', 'must-be-redacted', CONFIG['api_key'], 'must-never-send', 'SELECT secret', '整库不能外发', 'https://secret'):
        assert forbidden not in text
    assert packet['evidence'][0]['source']['file_name'] == '年度指标_模拟.csv'
    assert packet['evidence'][0]['fact']['value'] == '100'
    redacted = review.clean_review_text('文档 C:/Users/First Last/secret.csv。"api_key": "a quoted credential"; token=another-secret')
    assert 'First' not in redacted and 'Last/secret' not in redacted
    assert 'a quoted credential' not in redacted and 'another-secret' not in redacted


def test_answer_excerpt_is_sanitized_bounded_and_full_answer_changes_revision():
    first = entry()
    first['result']['answer'] = '待核对答案 /mnt/data/private.csv。' + '正文' * 1000 + '原结尾'
    first['result']['draft'] = '这份未使用草稿不发送'
    packet = review.build_review_packet(first)
    assert len(packet['answer_excerpt']) <= 1600
    assert '/mnt/' not in packet['answer_excerpt'] and packet['answer_excerpt_kind'] == 'answer'
    second = deepcopy(first)
    second['result']['answer'] = first['result']['answer'][:-3] + '新结尾'
    changed = review.build_review_packet(second)
    assert changed['answer_excerpt'] == packet['answer_excerpt']
    assert changed['revision'] != packet['revision']
    draft = entry()
    draft['result'].pop('answer')
    draft['result']['draft'] = '这是一段保存的候选草稿。'
    assert review.build_review_packet(draft)['answer_excerpt'] == draft['result']['draft']
    assert review.build_review_packet(draft)['answer_excerpt_kind'] == 'draft'


@pytest.mark.parametrize('path', ['/mnt/data/private.csv', '/opt/service/key.txt', '/srv/company/raw.xlsx',
                                  '/custom_root/secret.csv', '/root', '/secrets.json'])
def test_posix_paths_are_removed_from_question_answer_and_source_excerpt(path):
    saved = entry()
    saved['question'] += ' 文件位于' + path + '。'
    saved['result']['answer'] = '待审答案，位置' + path + '。'
    saved['result']['data_snapshot']['模拟公司'][0]['metric_provenance']['revenue']['snippet'] += '路径：' + path + '。'
    packet = review.build_review_packet(saved)
    assert path not in json.dumps(packet, ensure_ascii=False)
    assert '[路径已隐藏]' in packet['answer_excerpt']
    assert path not in review.clean_review_text('path:' + path)
    assert review.clean_review_text('每股收益100元/股') == '每股收益100元/股'


@pytest.mark.parametrize('text', ['营业收入100万元。', '营业收入2024亿元。', '营业收入2亿元。'])
def test_amounts_cannot_recombine_fact_raw_unit_year_or_page(text):
    saved = entry()
    source = saved['result']['data_snapshot']['模拟公司'][0]['metric_provenance']['revenue']
    source.update(raw_value='1000000', raw_unit='万元', page=2)
    packet = review.build_review_packet(saved)
    with pytest.raises(ValueError):
        review.validate_review_output(opinion(text), packet)
    assert review.validate_review_output(opinion('营业收入100亿元。'), packet)['notes']
    assert review.validate_review_output(opinion('原值1000000万元。'), packet)['notes']


def test_destination_identity_changes_for_provider_endpoint_model_but_not_key():
    original = review.review_destination_id(CONFIG)
    for key, value in [('provider', '新服务'), ('base_url', 'https://another.example/v1'), ('model', 'another-model')]:
        assert review.review_destination_id({**CONFIG, key: value}) != original
    assert review.review_destination_id({**CONFIG, 'api_key': 'different-test-placeholder'}) == original
    assert CONFIG['base_url'] not in original and CONFIG['api_key'] not in original


@pytest.mark.parametrize('bad', [
    opinion(refs=[]), opinion(refs=['E999']), opinion('营业收入999亿元。'),
    opinion('营业收入100万元。'), opinion('营业收入一百万元。'),
    opinion('请打开 C:/private/key.txt'), opinion('来源E002可以证明结果。'),
    json.dumps({'notes': [], 'approved': True}),
])
def test_invalid_model_output_is_rejected(bad):
    with pytest.raises(ValueError):
        review.validate_review_output(bad, review.build_review_packet(entry()))


def test_numbers_must_belong_to_the_particular_cited_evidence():
    original = entry()
    original['result']['data_snapshot']['模拟公司'].append({'year': 2023, 'revenue': 80,
        'metric_provenance': {'revenue': {'file_name': '年度指标_模拟.csv', 'cell': 'B1', 'raw_value': '80', 'raw_unit': '亿元'}}})
    packet = review.build_review_packet(original)
    with pytest.raises(ValueError):
        review.validate_review_output(opinion('营业收入80亿元。', ['E001']), packet)
    assert review.validate_review_output(opinion('营业收入80亿元。', ['E002']), packet)['notes']


def test_failure_rejects_invalid_role_and_skips_dependent_calls_without_raw_error():
    calls = []
    def transport(*args, **kwargs):
        calls.append(True)
        return opinion() if len(calls) == 1 else opinion('原值99999亿元。')
    result = review.run_multi_agent_review(entry(), CONFIG, confirmed=True, transport=transport)
    assert len(calls) == 2
    assert [role['status'] for role in result['roles']] == ['reviewed', 'rejected', 'skipped']
    assert '99999' not in json.dumps(result, ensure_ascii=False)
    assert any(event['status'] == 'returned' and event['role'] == 'critic' for event in result['events'])


@pytest.mark.parametrize('confirmed,config,item,expected', [
    (False, CONFIG, entry(), 'unconfirmed'), (True, {}, entry(), 'unconfigured'),
    (True, CONFIG, {'question': '没有来源', 'result': {'answer': '不可独立复核'}}, 'no_evidence'),
])
def test_no_consent_no_config_or_no_evidence_never_calls_transport(confirmed, config, item, expected):
    def forbidden(*args, **kwargs):
        raise AssertionError('Network must not run')
    result = review.run_multi_agent_review(item, config, confirmed=confirmed, transport=forbidden)
    assert result['status'] == expected
    assert all(role['status'] == 'skipped' for role in result['roles'])
    assert all(event['status'] == 'skipped' for event in result['events'])


def test_actual_budget_overrun_is_recorded_and_stops_later_roles():
    now = [0.0]
    calls = []
    def transport(*args, **kwargs):
        calls.append(True)
        now[0] += 56
        return opinion()
    result = review.run_multi_agent_review(entry(), CONFIG, confirmed=True, transport=transport, clock=lambda: now[0])
    assert len(calls) == 1 and result['elapsed_ms'] == 56000
    assert [role['status'] for role in result['roles']] == ['budget_exceeded', 'skipped', 'skipped']
    assert result['budget']['exceeded'] and result['status'] == 'incomplete'


def test_provider_error_and_unexpected_error_are_fixed_public_messages():
    def failed(*args, **kwargs):
        raise LLMRequestError('network')
    result = review.run_multi_agent_review(entry(), CONFIG, confirmed=True, transport=failed)
    assert result['roles'][0]['status'] == 'failed' and '未连接' in result['message']
    def unexpected(*args, **kwargs):
        raise RuntimeError('C:/private/secrets ' + CONFIG['api_key'])
    result = review.run_multi_agent_review(entry(), CONFIG, confirmed=True, transport=unexpected)
    text = json.dumps(result, ensure_ascii=False)
    assert 'C:/private' not in text and CONFIG['api_key'] not in text


def _app(config, saved=None):
    source = '''
import json
import streamlit as st
from app.multi_agent_review import render_multi_agent_review
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = json.loads(RECORDS_LITERAL)
if '_review_test_config' not in st.session_state:
    st.session_state._review_test_config = json.loads(CONFIG_LITERAL)
st.session_state.active_session_id = 'isolated-review-test'
render_multi_agent_review(st.session_state._review_test_config)
'''.replace('RECORDS_LITERAL', repr(json.dumps(saved or [], ensure_ascii=False))).replace('CONFIG_LITERAL', repr(json.dumps(config)))
    return AppTest.from_string(source, default_timeout=30).run()


def test_native_page_requires_answer_configuration_and_explicit_consent(monkeypatch):
    calls = []
    def transport(*args, **kwargs):
        calls.append(args)
        return opinion()
    monkeypatch.setattr(review, '_post_chat', transport)
    empty = _app({})
    assert not empty.exception and empty.button(key='agent_review_run_empty').disabled
    unconfigured = _app({}, [entry()])
    assert not unconfigured.exception and unconfigured.button(key='agent_review_run').disabled
    app = _app(CONFIG, [entry()])
    assert not app.exception and app.button(key='agent_review_run').disabled and not calls
    before = deepcopy(app.session_state.chat_messages)
    app.checkbox[0].check().run()
    assert not app.button(key='agent_review_run').disabled and not calls
    app.button(key='agent_review_run').click().run()
    assert not app.exception and len(calls) == 3
    assert app.session_state.chat_messages == before
    records = app.session_state.multi_agent_review_records
    assert next(iter(records.values()))['status'] == 'opinions_ready'
    app.radio[0].set_value('critic').run()
    assert not app.exception and len(calls) == 3
    app.session_state._review_test_config = {**CONFIG, 'model': 'a-different-model'}
    app.run()
    assert not app.exception and len(calls) == 3
    assert not app.radio, 'another model must not display the prior current review'
    assert app.button(key='agent_review_run').disabled and not app.checkbox[0].value
    assert len(app.session_state.multi_agent_review_records) == 1
