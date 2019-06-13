# coding: utf-8
from curs.utils.config import *

def main():
    data = load_yaml("config.yml")
    print (data["base"])
    # pass


if __name__ == "__main__":
    main()