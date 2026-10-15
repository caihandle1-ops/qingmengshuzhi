"""Build a pinned 50-company, 2021--2025 data pack from a local public snapshot.

This command is offline and deterministic. It does not execute during app startup.
It preserves the catalog's 50 identities and uses new five-year CSV file names. Provider rows retain
their disclosure/update versions; EPS is not rebased to a common share count.
Amounts exported in CNY 100 million; ratios in percentage points; EPS in CNY/share.
"""
from __future__ import annotations
import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

HERE = Path(__file__).resolve().parent
API = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
AS_OF = '2026-10-14'
YEARS = (2021, 2022, 2023, 2024, 2025)
SNAPSHOT_NAME = 'builtin_public_financials_20261014.json'
FIELDS = {'revenue': 'OPERATE_INCOME_PK', 'net_profit': 'PARENTNETPROFIT',
          'operating_cashflow': 'NETCASH_OPERATE_PK', 'roe': 'ROEJQ',
          'debt_ratio': 'ZCFZL', 'gross_margin': 'XSMLL', 'eps': 'EPSJB'}
AMOUNTS = {'revenue', 'net_profit', 'operating_cashflow'}
VERSION_POLICY = '截至2026-10-14东方财富各历史报告期披露版本；不统一追溯至同一报告版本或股本基础'
EPS_NOTE = '保留上游历史报告期基本每股收益；送转股等因素可能使各年股本基础不同，不宜直接作未调整的增长率比较。'
SPECIAL_EPS = {
    ('002594', 2023): '上游2023期EPS为10.32；比亚迪2025年报按2025年7月送转股调整后列示2023期EPS为3.44。本数据保留上游10.32，二者股本基础不同。',
    ('300750', 2021): '上游2021期EPS为6.8760；宁德时代2023年报经资本公积转增重算后的2021期EPS为3.8200。本数据保留上游6.8760。',
    ('300750', 2022): '上游2022期EPS为7.1766，与宁德时代2023年报转增调整后数一致；2022年报原披露数为12.9178。',
}

def decimal(value):
    if value is None or value == '': raise ValueError('Missing required financial metric')
    result = Decimal(str(value))
    if not result.is_finite(): raise ValueError('Non-finite financial metric')
    return result

def near(first, second, absolute='0.000001', relative='0.000000001'):
    a,b=decimal(first),decimal(second)
    return abs(a-b) <= max(Decimal(absolute),abs(b)*Decimal(relative))

def params_for(code):
    return dict(reportName='RPT_F10_FINANCE_MAINFINADATA',
                columns='SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,ORG_TYPE,REPORT_DATE,REPORT_TYPE,NOTICE_DATE,UPDATE_DATE,CURRENCY,'+','.join(FIELDS.values()),
                filter='(SECURITY_CODE="'+code+'")'+'(REPORT_DATE in ('+','.join("'"+str(y)+"-12-31'" for y in YEARS)+'))',
                pageSize=500,pageNumber=1,source='WEB',client='WEB')

def validate(snapshot):
    companies=snapshot['companies']
    codes={c['stock_code'] for c in companies}
    filenames={c['file_name'] for c in companies}
    if len(companies)!=50 or len(codes)!=50 or len(filenames)!=50: raise ValueError('Expected 50 unique companies and CSV paths')
    if snapshot['years']!=list(YEARS) or snapshot['as_of']!=AS_OF: raise ValueError('Unexpected snapshot years or cutoff')
    if snapshot.get('errors'): raise ValueError('Snapshot download errors')
    for filename in filenames:
        if Path(filename).name != filename or not filename.endswith('.csv'): raise ValueError('Unsafe CSV filename')
    profiles={r['SECURITY_CODE']:r for r in snapshot['tables']['profiles']}
    if len(snapshot['tables']['profiles'])!=50 or set(profiles)!=codes: raise ValueError('Profile coverage mismatch')
    expected={(code,year) for code in codes for year in YEARS}
    keyed={}
    residuals=[]
    for table in ('metrics','income','balance','cashflow'):
        keyed[table]={}
        for row in snapshot['tables'][table]:
            key=row['SECURITY_CODE'],int(row['REPORT_DATE'][:4])
            if key in keyed[table] or key not in expected: raise ValueError(f'{table}: duplicate/unexpected row {key}')
            if row['CURRENCY']!='CNY' or row['REPORT_TYPE']!='年报' or row['REPORT_DATE'][5:10]!='12-31':
                raise ValueError(f'{table}: incompatible currency/period {key}')
            for date_field in ('NOTICE_DATE','UPDATE_DATE'):
                if not row.get(date_field) or row[date_field][:10]>AS_OF: raise ValueError(f'{table}: invalid date {date_field} {key}')
            keyed[table][key]=row
        if set(keyed[table])!=expected: raise ValueError(f'{table}: expected 250 complete company/year pairs')
    for key,m in keyed['metrics'].items():
        i,b,c=(keyed[t][key] for t in ('income','balance','cashflow'))
        for field in FIELDS.values(): decimal(m.get(field))
        for label,first,second in (
            ('revenue',m['OPERATE_INCOME_PK'],i['OPERATE_INCOME']),
            ('parent_net_profit',m['PARENTNETPROFIT'],i['PARENT_NETPROFIT']),
            ('eps',m['EPSJB'],i['BASIC_EPS']),
            ('operating_cashflow',m['NETCASH_OPERATE_PK'],c['NETCASH_OPERATE']),
            ('assets',m['TOTAL_ASSETS_PK'],b['TOTAL_ASSETS'])):
            if not near(first,second): raise ValueError(f'{key}: inconsistent {label}')
        computed_margin=(decimal(i['OPERATE_INCOME'])-decimal(i['OPERATE_COST']))/decimal(i['OPERATE_INCOME'])*100
        computed_debt=decimal(b['TOTAL_LIABILITIES'])/decimal(b['TOTAL_ASSETS'])*100
        if not near(m['XSMLL'],computed_margin,absolute='.005',relative='0'): raise ValueError(f'{key}: gross margin mismatch')
        if not near(m['ZCFZL'],computed_debt,absolute='.005',relative='0'): raise ValueError(f'{key}: debt ratio mismatch')
        if i.get('MINORITY_INTEREST') is not None:
            residual=decimal(i['PARENT_NETPROFIT'])+decimal(i['MINORITY_INTEREST'])-decimal(i['NETPROFIT'])
            if residual:
                residuals.append(dict(code=key[0],year=key[1],residual_yuan=str(residual)))
            # Structured figures rounded from reports in thousands/ten-thousands
            # can have small additive residuals. Never modify or force-balance them.
            if abs(residual)>max(Decimal('1'),abs(decimal(i['NETPROFIT']))*Decimal('0.0000001')):
                raise ValueError(f'{key}: consolidated/parent/minority identity exceeds rounding tolerance')
    return profiles,keyed,residuals

def official_spot_checks(keyed):
    sources={
        'byd2022':'https://static.cninfo.com.cn/finalpage/2023-03-29/1216246589.PDF',
        'catl2022':'https://static.cninfo.com.cn/finalpage/2023-03-10/1216084559.PDF',
        'catl2023':'https://static.cninfo.com.cn/finalpage/2024-03-16/1219313048.PDF',
        'byd2025':'https://static.cninfo.com.cn/finalpage/2026-03-27/1225046995.PDF',
    }
    expected=[
        ('002594',2021,'byd2022',('216142395000','3045188000','65466682000','3.73','1.06')),
        ('002594',2022,'byd2022',('424060635000','16622448000','140837657000','16.14','5.71')),
        ('300750',2021,'catl2022',('130355796400','15931317900','42908008700','21.52','6.8760')),
        ('300750',2022,'catl2022',('328593987500','30729163500','61208843300','24.67',None)),
    ]
    checks=[]
    for code,year,source,values in expected:
        m=keyed['metrics'][code,year]
        for field,value in zip(('OPERATE_INCOME_PK','PARENTNETPROFIT','NETCASH_OPERATE_PK','ROEJQ','EPSJB'),values):
            if value is None: continue
            if decimal(m[field])!=decimal(value): raise ValueError(f'Official report spot-check failed {code} {year} {field}')
            checks.append(dict(code=code,year=year,field=field,expected=value,source_url=sources[source],status='pass'))
    m=keyed['metrics']['300750',2022]
    if decimal(m['EPSJB'])!=Decimal('7.1766'): raise ValueError('CATL 2022 adjusted EPS mismatch')
    checks.append(dict(code='300750',year=2022,field='EPSJB',expected='7.1766',source_url=sources['catl2023'],status='pass',
                       note='2023 annual report comparison after share capitalization; originally 12.9178 in 2022 annual report'))
    return {'scope':'Two issuers, 2021/2022 core figures; 20 field checks. Not a manual verification of all 250 annual reports.',
            'sources':sources,'checks':checks}

def build(snapshot_path, output):
    raw=snapshot_path.read_bytes()
    snapshot=json.loads(raw.decode('utf-8'))
    profiles,keyed,residuals=validate(snapshot)
    official=official_spot_checks(keyed)
    output.mkdir(parents=True,exist_ok=True)
    provenance=output/'provenance'
    provenance.mkdir(exist_ok=True)
    (provenance/SNAPSHOT_NAME).write_bytes(raw)
    columns=['year',*FIELDS,'audit_opinion','raw_source','source_url','source_notice_date','source_update_date','source_currency',
             'source_provider','source_snapshot','source_retrieved_at',*('source_'+f+'_field' for f in FIELDS),*('raw_'+f for f in FIELDS),
             'source_net_profit_definition','source_version_policy','source_version_note','source_eps_note']
    catalog_companies=[]
    for company in snapshot['companies']:
        code=company['stock_code']
        filename='sample_'+code+'_2021_2025.csv'
        catalog_company=dict(company,file_name=filename)
        catalog_company['aliases']=list(dict.fromkeys([*company.get('aliases',[]),profiles[code]['SECURITY_NAME_ABBR']]))
        if profiles[code]['ORG_NAME']!=company['name']:
            catalog_company['aliases'].append(profiles[code]['ORG_NAME'])
            catalog_company['aliases']=list(dict.fromkeys(catalog_company['aliases']))
        catalog_companies.append(catalog_company)
        with (output/filename).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=columns)
            writer.writeheader()
            for year in YEARS:
                m=keyed['metrics'][code,year]
                note=SPECIAL_EPS.get((code,year),EPS_NOTE)
                row=dict(year=year,audit_opinion='',source_url=API+'?'+urlencode(params_for(code)),source_notice_date=m['NOTICE_DATE'][:10],
                         source_update_date=m['UPDATE_DATE'][:10],source_currency=m['CURRENCY'],source_provider=snapshot['provider'],
                         source_snapshot='data/provenance/'+SNAPSHOT_NAME,source_retrieved_at=snapshot['retrieved_at'],
                         source_net_profit_definition='归属于母公司股东的净利润（非合并净利润、非扣非净利润）',
                         source_version_policy=VERSION_POLICY,source_version_note=VERSION_POLICY+'；'+note,source_eps_note=note,
                         raw_source=f"{company['name']} {year}年报公开结构化财务数据；东方财富F10；采集截至{AS_OF}；营业收入、归母净利润、经营活动现金流量净额由元换算为亿元；ROE为加权平均净资产收益率；保留上游披露版本，未逐份人工核验年报原件；审计意见未核验，留空。版本说明：{VERSION_POLICY}。EPS注记：{note}")
                for metric,field in FIELDS.items():
                    value=decimal(m[field])
                    row[metric]=format(value/Decimal(100000000) if metric in AMOUNTS else value,'f')
                    row['raw_'+metric]=format(value,'f')
                    row['source_'+metric+'_field']=field
                writer.writerow(row)
    catalog={'schema_version':1,'companies':catalog_companies}
    (output/'builtin_companies.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (provenance/'official_spot_checks_20261014.json').write_text(json.dumps(official,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    validation=dict(status='pass',companies=50,years=list(YEARS),annual_rows=250,required_metric_values=1750,
                    missing_required_values=0,duplicate_rows=0,cross_table_pairs_checked=250,official_field_spot_checks=20,
                    snapshot_sha256=hashlib.sha256(raw).hexdigest(),net_profit_identity_rounding_residuals=residuals,
                    amount_unit='亿元 CNY',ratio_unit='percentage points',eps_unit='CNY/share',
                    version_policy=VERSION_POLICY,audit_opinion_policy='Unverified audit opinions left blank',
                    manual_review_scope='Official report spot-checks only; not all 250 annual reports manually verified')
    (provenance/'build_validation_20261014.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(validation,ensure_ascii=False,indent=2))
    return validation

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,default=HERE.parent/'data/provenance'/SNAPSHOT_NAME)
    parser.add_argument('--output',type=Path,required=True,help='Explicit destination for the reconstructed data pack; application runtime data is never touched')
    args=parser.parse_args()
    build(args.snapshot,args.output)
