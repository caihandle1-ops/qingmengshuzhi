import base64
import hashlib
from html.parser import HTMLParser
import json
import sqlite3
from pathlib import Path
import re
import shutil
import subprocess
from unittest.mock import patch
from xml.etree import ElementTree

import pytest

from app.system_explorer import MODULES, architecture_svg, schema_svg
from core.db import get_db_path, init_db
from core.storage import workspace_context
from core.system_schema import _authorizer, read_system_schema


def test_live_schema_reports_real_fields_keys_and_partial_index_without_writes(tmp_path):
    with workspace_context('evaluation', tmp_path, allow_writes=True):
        init_db(migrate_legacy=False)
        path = get_db_path()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        modified = path.stat().st_mtime_ns
        snapshot = read_system_schema()
        assert snapshot['status'] == 'ready'
        assert snapshot['read_only'] is True
        assert snapshot['user_version'] == 6
        tables = {table['name']: table for table in snapshot['tables']}
        assert set(tables) == {'companies', 'financial_metrics', 'report_files', 'metric_sources', 'app_meta', 'scope_probe_facts'}
        fields = {field['name']: field for field in tables['financial_metrics']['fields']}
        assert fields['id']['primary_key_order'] == 1
        assert fields['company_id']['type'] == 'INTEGER'
        assert fields['company_id']['not_null'] is True
        assert 'consolidated_net_profit' in fields
        assert {'from_table': 'financial_metrics', 'from': 'company_id', 'to_table': 'companies', 'to_field': 'id',
                'on_update': 'NO ACTION', 'on_delete': 'NO ACTION'} in snapshot['relations']
        current = next(index for index in tables['metric_sources']['indexes'] if index['name'] == 'metric_sources_current')
        assert current['unique'] is True and current['partial'] is True
        assert current['columns'] == ['company_id', 'year', 'metric']
        assert current['predicate'] == 'is_current=1'
        assert any(index['unique'] and index['columns'] == ['name'] for index in tables['companies']['indexes'])
        assert path.stat().st_mtime_ns == modified
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        assert str(tmp_path) not in json.dumps(snapshot)


def test_metadata_export_omits_business_values_defaults_unapproved_tables_and_sql_secrets(tmp_path):
    path = tmp_path / 'investor_agent.db'
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE companies(id INTEGER PRIMARY KEY, name TEXT DEFAULT 'DEFAULT_SECRET');
        INSERT INTO companies VALUES(1, 'BUSINESS_SECRET');
        CREATE TABLE metric_sources(id INTEGER PRIMARY KEY, company_id INTEGER, year INTEGER, metric TEXT, is_current INTEGER, source_note TEXT);
        CREATE UNIQUE INDEX metric_sources_current ON metric_sources(company_id, year, metric)
            WHERE is_current=1 AND source_note='INDEX_SECRET';
        CREATE TABLE private_tokens(token TEXT);
        INSERT INTO private_tokens VALUES('TOKEN_SECRET');
    """)
    connection.close()
    with patch('core.system_schema.get_db_path', return_value=path):
        snapshot = read_system_schema()
    exported = json.dumps(snapshot, ensure_ascii=False)
    assert snapshot['status'] == 'ready'
    for secret in ('DEFAULT_SECRET', 'BUSINESS_SECRET', 'INDEX_SECRET', 'TOKEN_SECRET', 'private_tokens', str(tmp_path)):
        assert secret not in exported
    assert '<文字常量已隐藏>' in exported
    assert 'CREATE TABLE' not in exported


def test_missing_or_invalid_database_never_creates_files_or_discloses_path(tmp_path):
    missing = tmp_path / 'new-session' / 'investor_agent.db'
    with patch('core.system_schema.get_db_path', return_value=missing):
        snapshot = read_system_schema()
    assert snapshot['status'] == 'not_initialized'
    assert not missing.parent.exists()
    invalid = tmp_path / 'private-location.db'
    invalid.write_text('this is not a database', encoding='utf-8')
    with patch('core.system_schema.get_db_path', return_value=invalid):
        snapshot = read_system_schema()
    assert snapshot['status'] == 'unavailable'
    assert str(invalid) not in json.dumps(snapshot)


def test_authorizer_denies_business_reads_writes_and_pragma_mutation():
    connection = sqlite3.connect(':memory:')
    connection.execute('CREATE TABLE companies(id INTEGER)')
    connection.set_authorizer(_authorizer)
    for sql in ('SELECT * FROM companies', 'INSERT INTO companies VALUES(1)', 'DROP TABLE companies',
                'PRAGMA user_version=7', 'PRAGMA writable_schema=ON', "ATTACH DATABASE ':memory:' AS leak"):
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute(sql)
    assert connection.execute('PRAGMA table_info("companies")').fetchone()[1] == 'id'
    connection.close()


def test_architecture_catalog_matches_real_files_and_schema_diagram_only_draws_actual_tables():
    root = Path(__file__).resolve().parents[1]
    assert all((root / file).is_file() for _, file, _ in MODULES)
    graph = architecture_svg(collaboration_available=False)
    assert '当前构建未安装协作审查模块' in graph
    assert '不代表已执行记录' in graph
    assert '独立模型调用；用户主动运行' in architecture_svg(collaboration_available=True)
    graph = schema_svg({'tables': [{'name': 'companies', 'purpose': '<script>evil</script>', 'fields': [], 'foreign_keys': []}], 'relations': []})
    assert '&lt;script&gt;' in graph and '<script>' not in graph
    assert 'financial_metrics' not in graph
    assert '<path class="system-schema-edge"' not in graph


def _system_page(db_root):
    from app.system_explorer import render_system_explorer
    from core.storage import workspace_context
    with workspace_context('evaluation', db_root):
        render_system_explorer()


def _rendered_diagram(page, surface, expected_text):
    messages = [item.proto for item in page.get('html') if f'class="{surface}"' in item.proto.body]
    assert len(messages) == 1 and not messages[0].unsafe_allow_javascript

    class Images(HTMLParser):
        def __init__(self):
            super().__init__()
            self.images = []

        def handle_starttag(self, tag, attrs):
            if tag == 'img':
                self.images.append(dict(attrs))

    parser = Images()
    parser.feed(messages[0].body)
    assert len(parser.images) == 1
    image = parser.images[0]
    assert image['alt'] and image['src'].startswith('data:image/svg+xml;base64,')
    graph = base64.b64decode(image['src'].split(',', 1)[1], validate=True).decode('utf-8')
    root = ElementTree.fromstring(graph)
    assert root.tag == '{http://www.w3.org/2000/svg}svg'
    assert expected_text in ''.join(root.itertext())
    assert root.find('{http://www.w3.org/2000/svg}style') is not None
    assert int(image['height']) > 300 and int(image['width']) > 1000
    assert '<script' not in graph and '<foreignObject' not in graph
    return messages[0].body


def test_native_system_explorer_switches_views_fields_and_metadata_download(tmp_path):
    from streamlit.testing.v1 import AppTest
    with workspace_context('evaluation', tmp_path, allow_writes=True):
        init_db(migrate_legacy=False)
        connection = sqlite3.connect(get_db_path())
        connection.execute("INSERT INTO companies(name) VALUES('NEVER_DISPLAY_BUSINESS_NAME')")
        connection.commit()
        connection.close()
    page = AppTest.from_function(_system_page, args=(str(tmp_path),)).run()
    assert not page.exception
    assert page.radio(key='system_explorer_view').value == '系统架构'
    _rendered_diagram(page, 'system-map-surface', '工作界面')
    assert any('core/qa_engine.py' in frame.value.to_string() for frame in page.dataframe)
    page.radio(key='system_explorer_view').set_value('数据库结构').run()
    assert not page.exception
    assert page.selectbox(key='system_schema_table').value == 'companies'
    _rendered_diagram(page, 'system-schema-surface', 'financial_metrics')
    assert any('name' in frame.value.to_string() for frame in page.dataframe)
    page.selectbox(key='system_schema_table').set_value('metric_sources').run()
    assert not page.exception
    tables = '\n'.join(frame.value.to_string() for frame in page.dataframe)
    assert 'metric_sources_current' in tables and 'is_current=1' in tables
    assert 'NEVER_DISPLAY_BUSINESS_NAME' not in tables
    assert str(tmp_path) not in tables
    downloads = page.get('download_button')
    assert len(downloads) == 1
    assert downloads[0].proto.label == '下载当前结构 JSON'
    page.radio(key='system_explorer_view').set_value('系统架构').run()
    assert not page.exception


def test_actual_streamlit_sanitizer_preserves_both_decodable_diagram_images(tmp_path):
    """Use emitted Streamlit HTML and its installed HTML-only sanitizer."""
    import streamlit
    from streamlit.testing.v1 import AppTest
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the actual Streamlit sanitizer regression.')
    available = subprocess.run([node, '-e', "require.resolve('jsdom')"], capture_output=True, timeout=20)
    if available.returncode:
        pytest.skip('Set NODE_PATH to the offline jsdom installation for sanitizer integration.')
    with workspace_context('evaluation', tmp_path, allow_writes=True):
        init_db(migrate_legacy=False)
    page = AppTest.from_function(_system_page, args=(str(tmp_path),)).run()
    assert not page.exception
    architecture = _rendered_diagram(page, 'system-map-surface', '工作界面')
    page.radio(key='system_explorer_view').set_value('数据库结构').run()
    assert not page.exception
    schema = _rendered_diagram(page, 'system-schema-surface', 'financial_metrics')
    assets = Path(streamlit.__file__).parent / 'static' / 'static' / 'js'
    frontends = list(assets.glob('Html.*.js'))
    assert len(frontends) == 1
    frontend = frontends[0].read_text(encoding='utf-8')
    purifier_name = re.search(r'\./(purify\.es\.[^"\']+\.js)', frontend)
    assert purifier_name, 'Locate the actual installed Streamlit purifier.'
    fixture = tmp_path / 'system-diagrams-sanitized.json'
    fixture.write_text(json.dumps({'frontend': str(frontends[0]),
                                  'purifier': str(assets / purifier_name.group(1)),
                                  'diagrams': [{'html': architecture, 'text': '工作界面'},
                                               {'html': schema, 'text': 'financial_metrics'}]},
                                 ensure_ascii=True), encoding='utf-8')
    program = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
const fixture=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
const dom=new JSDOM('<!doctype html><html><body></body></html>',{runScripts:'outside-only'});
const win=dom.window,doc=win.document;
try {
  const source=fs.readFileSync(fixture.purifier,'utf8');
  const exported=/export\s*\{\s*([\w$]+)\s+as\s+t\s*\};?\s*$/;
  assert.match(source,exported);
  win.eval('(function(){'+source.replace(exported,'window.__purifier=$1;')+'\n})();');
  assert.match(fs.readFileSync(fixture.frontend,'utf8'),/USE_PROFILES:\{html:!0\},FORCE_BODY:!0/);
  const config={USE_PROFILES:{html:true},FORCE_BODY:true};
  for(const item of fixture.diagrams){
    const clean=win.__purifier.sanitize(item.html,config);
    doc.body.innerHTML=clean;
    const images=doc.querySelectorAll('img.system-diagram-image');
    assert.equal(images.length,1,'The actual HTML-only sanitizer must retain an image.');
    const image=images[0],src=image.getAttribute('src');
    assert.ok(image.alt.length>10);assert.match(src,/^data:image\/svg\+xml;base64,[A-Za-z0-9+/]+=*$/);
    const xml=Buffer.from(src.split(',')[1],'base64').toString('utf8');
    const graph=new win.DOMParser().parseFromString(xml,'image/svg+xml');
    assert.equal(graph.querySelector('parsererror'),null,'Embedded SVG must be valid XML.');
    assert.equal(graph.documentElement.namespaceURI,'http://www.w3.org/2000/svg');
    assert.ok(graph.documentElement.textContent.includes(item.text));
    assert.ok(graph.querySelectorAll('text').length>6);
    const style=graph.querySelector('style');assert.ok(style);assert.match(style.textContent,/fill:/);assert.match(style.textContent,/font:/);
    assert.ok(Number(image.getAttribute('height'))>300);
    assert.equal(graph.querySelector('script,foreignObject,image,iframe,use'),null);
    for(const el of graph.querySelectorAll('*'))for(const attr of el.attributes){
      assert.ok(!/^on/i.test(attr.name));assert.ok(!['href','xlink:href','src'].includes(attr.name));
    }
    assert.ok(!/https?:|@import/.test(style.textContent),'Styles must not request remote resources.');
    // Reproduce the original failure as a negative control with these exact bytes.
    const old=doc.createElement('div');old.innerHTML=win.__purifier.sanitize('<div>'+xml+'</div>',config);
    assert.equal(old.querySelector('svg'),null);
  }
  process.stdout.write('Both actual Streamlit diagram outputs survive sanitization and decode.');
} finally { win.close(); }
"""
    checked = subprocess.run([node, '-e', program, str(fixture)], capture_output=True,
                             text=True, encoding='utf-8', timeout=30)
    assert checked.returncode == 0, checked.stdout + checked.stderr
