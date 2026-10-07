from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class IssueOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; product_id:int; source:str; source_key:str; title:str
    risk_level:Literal['low','medium','high']; why:str; fix:str; recommended_text:str; placement:str
    status:Literal['pending','in_progress','resolved']; created_at:datetime

class IssueStatusUpdate(BaseModel):
    status:Literal['pending','in_progress','resolved']

class ScanRequest(BaseModel):
    product_id:int; content:str=Field(min_length=1); filename:str='pasted-content'

class ScanOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; product_id:int; filename:str; findings:list[dict]; created_at:datetime
