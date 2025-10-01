from pydantic import BaseModel
from typing import Optional, List, Dict
class ConnectRequest(BaseModel):
    channel: str
    bitrate: Optional[int] = None
class SendRequest(BaseModel):
    frames: List[Dict[str,str]]
class LogStartRequest(BaseModel):
    format: str = 'csv'
