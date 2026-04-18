# src/session_persistence.py
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from .models import InterviewSession, SlotValue, InterviewState, CustomEncoder, decode_session

class SessionPersistence:
    """会话持久化管理器，支持保存、恢复和列表查询"""
    
    def __init__(self, storage_dir: str = "data/sessions"):
        self.storage_dir = storage_dir
        # 确保目录存在
        os.makedirs(self.storage_dir, exist_ok=True)
    
    def save_session(self, session: InterviewSession) -> str:
        """保存会话"""
        filepath = os.path.join(self.storage_dir, f"{session.session_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            # 使用自定义编码器处理枚举和日期时间
            json.dump(session.model_dump(), f, ensure_ascii=False, indent=2, cls=CustomEncoder)
        print(f"会话已保存: {filepath}")  # 调试信息
        return filepath
    
    def load_session(self, session_id: str) -> Optional[InterviewSession]:
        """加载会话"""
        filepath = os.path.join(self.storage_dir, f"{session_id}.json")
        if not os.path.exists(filepath):
            print(f"会话文件不存在: {filepath}")  # 调试信息
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 解码枚举和日期时间
        data = decode_session(data)
        return InterviewSession(**data)
    
    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """获取所有会话摘要"""
        sessions = []
        if not os.path.exists(self.storage_dir):
            return sessions
        
        for filename in os.listdir(self.storage_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.storage_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    sessions.append({
                        'session_id': data.get('session_id'),
                        'scenario_type': data.get('scenario_type'),
                        'start_time': data.get('start_time'),
                        'is_complete': data.get('is_complete', False)
                    })
        return sorted(sessions, key=lambda x: x.get('start_time', ''), reverse=True)
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        filepath = os.path.join(self.storage_dir, f"{session_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False