from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ArticleResponse(BaseModel):
    id: int
    title: str
    content: Optional[str]
    processed_content: Optional[str]
    source_url: str
    group_id: Optional[str]
    processed: bool
    brand_name: Optional[str]
    model_name: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]
    
    class Config:
        from_attributes = True
        protected_namespaces = ()