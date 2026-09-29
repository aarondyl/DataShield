"""Developer Describe → Scan → Fix → Ship workflow APIs."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import DeveloperIssue, Product, SdkScan
from app.schemas.developer import IssueOut, IssueStatusUpdate, ScanOut, ScanRequest
from app.core.llm import get_llm_client_safe

router=APIRouter(prefix='/developer',tags=['developer'])

RULES=[
 ('firebase','Firebase Analytics','sdk','medium','设备标识符和使用行为','Firebase Analytics 可能处理设备标识符和使用行为。','在隐私政策“第三方服务”中披露服务商、数据类型、用途和隐私政策链接。'),
 ('sentry','Sentry','sdk','medium','设备及错误日志','Sentry 可能收集设备信息、IP 地址和错误日志。','在第三方服务清单中披露 Sentry，并核对采样与脱敏配置。'),
 ('android.permission.access_fine_location','Location Permission','permission','high','精确位置','精确定位属于敏感个人信息，需要明确目的并取得单独同意。','说明位置数据用途、使用场景和关闭方式，仅在需要时请求权限。'),
 ('nslocation','Location Permission','permission','high','位置数据','iOS 定位权限涉及敏感个人信息。','补充位置用途说明，并配置清晰的系统权限提示文案。'),
 ('android.permission.camera','Camera Permission','permission','medium','相机数据','相机权限可能采集图像或视频。','说明相机使用场景，并仅在用户主动使用功能时请求权限。'),
 ('nscamerausagedescription','Camera Permission','permission','medium','相机数据','iOS 相机权限需要与实际功能和披露保持一致。','在隐私政策中说明相机用途与处理方式。'),
 ('android.permission.read_contacts','Contacts Permission','permission','high','通讯录','通讯录包含大量第三方个人信息。','说明必要性、处理范围与保护措施，避免全量读取。'),
 ('facebook','Meta/Facebook SDK','sdk','medium','设备标识符和使用行为','广告或分析 SDK 可能跟踪用户行为。','在第三方 SDK 清单中披露，并提供选择或退出机制。'),
 ('stripe','Stripe','sdk','medium','支付与交易信息','支付 SDK 会处理交易和设备信息。','说明支付服务商、共享字段和处理目的。'),
]

def upsert_issue(db:Session, product_id:int, source:str, key:str, title:str, level:str, why:str, fix:str, text:str='', placement:str=''):
    issue=db.scalar(select(DeveloperIssue).where(DeveloperIssue.product_id==product_id,DeveloperIssue.source==source,DeveloperIssue.source_key==key))
    if issue is None:
        issue=DeveloperIssue(product_id=product_id,source=source,source_key=key,title=title)
        db.add(issue)
    issue.risk_level=level; issue.why=why; issue.fix=fix; issue.recommended_text=text; issue.placement=placement
    return issue

@router.get('/issues',response_model=list[IssueOut])
def issues(product_id:int|None=None,db:Session=Depends(get_db)):
    stmt=select(DeveloperIssue).order_by(DeveloperIssue.id.desc())
    if product_id is not None: stmt=stmt.where(DeveloperIssue.product_id==product_id)
    return list(db.scalars(stmt).all())

@router.patch('/issues/{issue_id}',response_model=IssueOut)
def update_issue(issue_id:int,payload:IssueStatusUpdate,db:Session=Depends(get_db)):
    issue=db.get(DeveloperIssue,issue_id)
    if issue is None: raise HTTPException(404,'整改事项不存在')
    issue.status=payload.status; db.commit(); db.refresh(issue); return issue

@router.post('/sdk-scan',response_model=ScanOut,status_code=201)
def scan(payload:ScanRequest,db:Session=Depends(get_db)):
    product=db.get(Product,payload.product_id)
    if product is None: raise HTTPException(404,'产品不存在')
    content=payload.content.lower(); policy=(product.privacy_policy_text or '').lower(); findings=[]
    for needle,name,kind,level,data,why,fix in RULES:
        if needle not in content: continue
        disclosed=any(word in policy for word in [name.lower(),data.lower(),name.split()[0].lower()])
        finding={'key':needle,'name':name,'kind':kind,'risk_level':level,'data':data,'why':why,'fix':fix,'policy_disclosed':disclosed}
        findings.append(finding)
        if not disclosed:
            upsert_issue(db,product.id,'sdk-scan',needle,f'补充 {name} 披露',level,why,fix,f'{name} 可能处理{data}，用于提供相关产品功能。','隐私政策的“第三方服务 / SDK 清单”部分')
    # When a real provider is configured, let it refine the rule explanations.
    # Deterministic text above remains the reliable fallback for mock/offline use.
    client = get_llm_client_safe()
    if findings and client.provider_name == 'api':
        try:
            explained = client.chat_json('你是开发者隐私合规助手。仅返回 JSON：{"items":[{"key":"...","why":"...","fix":"..."}]}。不得声称保证合规。', f'结合产品画像解释这些扫描结果：{findings}', context={'task':'sdk-explain'})
            by_key = {item.get('key'): item for item in explained.get('items', [])}
            for finding in findings:
                if finding['key'] in by_key:
                    finding['why'] = by_key[finding['key']].get('why') or finding['why']
                    finding['fix'] = by_key[finding['key']].get('fix') or finding['fix']
        except Exception:
            pass
    sdk_names=[f['name'] for f in findings if f['kind']=='sdk']
    if sdk_names:
        product.uses_third_party_sdk=True
        product.third_party_sdks=sorted(set((product.third_party_sdks or [])+sdk_names))
    if any(f['key'] in {'android.permission.access_fine_location','nslocation'} for f in findings): product.collects_location_data=True
    item=SdkScan(product_id=product.id,filename=payload.filename,content=payload.content,findings=findings)
    db.add(item); db.commit(); db.refresh(item); return item
