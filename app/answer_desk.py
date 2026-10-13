"""Decorative reading-desk metadata; financial values stay in native views."""
from hashlib import sha256
from html import escape
from pathlib import PureWindowsPath


def _id(value):
    return sha256(str(value).encode('utf-8')).hexdigest()[:24]


def answer_desk_heading(question, key):
    return (f'<header class="qm-answer-desk-heading" data-desk-scene="answer" data-desk-id="{_id(key)}">'
            '<div><span>RESEARCH / FINDINGS</span><h3>答案与依据</h3></div>'
            f'<p>{escape(str(question))}</p><i data-desk-line aria-hidden="true"></i></header>')


def evidence_rest_html(sources, key):
    names = list(dict.fromkeys(PureWindowsPath(str(entry['source'].get('file_name') or '来源未标注')).name for entry in sources))
    preview = ''.join(f'<li>{escape(name)}</li>' for name in names[:3])
    note = '选择上方来源或核验，和答案并排阅读。' if sources else '当前回答未保存引用；需要补充来源后再核验。'
    return (f'<section class="qm-evidence-rest" data-desk-scene="evidence" data-desk-id="{_id(key)}">'
            '<div class="qm-evidence-rest-art" aria-hidden="true"><i data-desk-piece></i>'
            '<i data-desk-piece></i><i data-desk-piece></i></div>'
            f'<span>依据目录</span><ul>{preview}</ul><p>{note}</p></section>')


def import_file_art(model):
    # State labels derive exclusively from the existing import state machine.
    identity = _id(model['content_key'])
    state = escape(str(model['state']), quote=True)
    label = escape(str(model['file_type'])) if model.get('filename') else 'FILE'
    return (f'<div class="qm-file-object" data-desk-scene="import" data-desk-id="{identity}" data-file-state="{state}" aria-hidden="true">'
            '<i class="qm-file-shadow" data-desk-piece></i><i class="qm-file-sheet" data-desk-piece></i>'
            f'<i class="qm-file-face" data-desk-piece><b>{label}</b><em></em><em></em><em></em></i></div>')
