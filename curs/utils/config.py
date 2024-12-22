# coding: utf-8
import codecs
import yaml
import os

def load_yaml(config_filename):
    with codecs.open(config_filename, encoding='utf-8') as f:
        return yaml.load(f,Loader=yaml.FullLoader)