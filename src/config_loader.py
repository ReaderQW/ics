import json
import os
from copy import deepcopy
from typing import Dict, Any, List
from .models import ScenarioConfig

class ConfigLoader:
    def __init__(self, config_dir: str = "config/scenarios"):
        self.config_dir = config_dir
        self.cache: Dict[str, ScenarioConfig] = {}
    
    def load_scenario(self, scenario_type: str, shop_name: str | None = None) -> ScenarioConfig:
        """加载指定场景的配置"""
        cache_key = f"{scenario_type}:{shop_name or ''}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        if scenario_type in self.cache:
            base_config = self.cache[scenario_type]
        else:
            config_path = os.path.join(self.config_dir, f"{scenario_type}.json")
        
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"配置文件不存在: {config_path}")

            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            base_config = ScenarioConfig(**data)
            self.cache[scenario_type] = base_config

        config_data = deepcopy(base_config.model_dump())
        config_data = self._apply_shop_name(config_data, shop_name or "该商铺")

        config = ScenarioConfig(**config_data)
        self.cache[cache_key] = config
        return config
    
    def get_available_scenarios(self) -> List[str]:
        """获取所有可用的场景类型"""
        if not os.path.exists(self.config_dir):
            return []
        
        files = [f.replace('.json', '') for f in os.listdir(self.config_dir) 
                 if f.endswith('.json')]
        return files

    def get_shop_options(self, scenario_type: str) -> List[str]:
        """获取场景下可选店铺列表"""
        config = self.load_scenario(scenario_type)
        return config.shop_options or []

    def _apply_shop_name(self, data: Dict[str, Any], shop_name: str) -> Dict[str, Any]:
        """将配置中的 {shop_name} 占位符替换为具体店铺名"""
        if isinstance(data, dict):
            return {k: self._apply_shop_name(v, shop_name) for k, v in data.items()}
        if isinstance(data, list):
            return [self._apply_shop_name(i, shop_name) for i in data]
        if isinstance(data, str):
            return data.replace("{shop_name}", shop_name)
        return data