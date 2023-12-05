# coding: utf-8
import codecs
import yaml

def load_yaml(path):
    with codecs.open(path, encoding='utf-8') as f:
        return yaml.load(f,Loader=yaml.FullLoader)