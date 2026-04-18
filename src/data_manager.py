import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from .models import InterviewSession

class DataManager:
    def __init__(self, storage_dir: str = "data/sessions"):
        self.storage_dir = storage_dir
        import os
        os.makedirs(storage_dir, exist_ok=True)
    
    def create_session(self, scenario_type: str) -> str:
        """创建新的访谈会话"""
        session_id = str(uuid.uuid4())[:8]
        session = InterviewSession(
            session_id=session_id,
            scenario_type=scenario_type
        )
        self._save_session(session)
        return session_id
    
    def get_session(self, session_id: str) -> Optional[InterviewSession]:
        """获取会话数据"""
        import os
        filepath = f"{self.storage_dir}/{session_id}.json"
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return InterviewSession(**data)
    
    def update_session(self, session: InterviewSession):
        """更新会话数据"""
        self._save_session(session)
    
    def _save_session(self, session: InterviewSession):
        """保存会话到文件"""
        filepath = f"{self.storage_dir}/{session.session_id}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(session.model_dump(), f, ensure_ascii=False, indent=2, default=str)
    
    def get_all_sessions(self) -> List[InterviewSession]:
        """获取所有会话"""
        import os
        sessions = []
        for filename in os.listdir(self.storage_dir):
            if filename.endswith('.json'):
                with open(f"{self.storage_dir}/{filename}", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    sessions.append(InterviewSession(**data))
        return sessions