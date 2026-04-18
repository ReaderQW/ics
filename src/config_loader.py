import json
import os
from typing import Dict, Any, List
from .models import ScenarioConfig

class ConfigLoader:
    def __init__(self, config_dir: str = "config/scenarios"):
        self.config_dir = config_dir
        self.cache: Dict[str, ScenarioConfig] = {}
    
    def load_scenario(self, scenario_type: str) -> ScenarioConfig:
        """加载指定场景的配置"""
        if scenario_type in self.cache:
            return self.cache[scenario_type]
        
        config_path = os.path.join(self.config_dir, f"{scenario_type}.json")
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        config = ScenarioConfig(**data)
        self.cache[scenario_type] = config
        return config
    
    def get_available_scenarios(self) -> List[str]:
        """获取所有可用的场景类型"""
        if not os.path.exists(self.config_dir):
            return []
        
        files = [f.replace('.json', '') for f in os.listdir(self.config_dir) 
                 if f.endswith('.json')]
        return files