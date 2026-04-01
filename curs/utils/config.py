# coding: utf-8
import codecs
import yaml
import os
import logging

logger = logging.getLogger(__name__)

def load_yaml(config_filename):
    with codecs.open(config_filename, encoding='utf-8') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    
    # 尝试加载本地覆盖配置
    base_path = os.path.splitext(config_filename)[0]
    local_path = f"{base_path}.local.yml"
    
    if os.path.exists(local_path):
        logger.info(f"加载本地配置: {local_path}")
        with codecs.open(local_path, encoding='utf-8') as f:
            local_config = yaml.load(f, Loader=yaml.FullLoader)
        
        # 合并配置
        if local_config:
            _merge_config(config, local_config)
    
    # 支持环境变量覆盖
    _load_env_overrides(config)
    
    return config

def _merge_config(base, override):
    """递归合并配置"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _merge_config(base[key], value)
        else:
            base[key] = value

def _load_env_overrides(config):
    """从环境变量加载配置覆盖"""
    # 数据库配置
    if 'database' not in config:
        config['database'] = {}
    
    db_env_map = {
        'CURS_DB_HOST': 'host',
        'CURS_DB_PORT': 'port',
        'CURS_DB_NAME': 'database',
        'CURS_DB_USER': 'user',
        'CURS_DB_PASSWORD': 'password',
    }
    for env_key, config_key in db_env_map.items():
        value = os.environ.get(env_key)
        if value:
            config['database'][config_key] = value
    
    # QMT 配置
    if 'qmt' not in config:
        config['qmt'] = {}
    
    qmt_env_map = {
        'CURS_QMT_PATH': 'path',
        'CURS_QMT_ACCOUNT_ID': 'account_id',
        'CURS_QMT_TRADER_NAME': 'trader_name',
    }
    for env_key, config_key in qmt_env_map.items():
        value = os.environ.get(env_key)
        if value:
            config['qmt'][config_key] = value
