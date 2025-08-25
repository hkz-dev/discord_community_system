# mod_getPath.py
import os

# ベースディレクトリ
base_dir = os.path.dirname(os.path.abspath(__file__))

# 共通で使う設定ファイルのパス
def get_inifile_path(filename="set.ini"):
    return os.path.join(base_dir, filename)


# core.logのファイルパス
def get_core_logfile_path(filename="core.log"):
    return os.path.join(base_dir,filename)

# roomer.logファイルのパス
def get_roomer_logfile_path(filename="roomer.log"):
    return os.path.join(base_dir, filename)

# navigator.logのファイルパス
def get_navigator_logfile_path(filename="navigator.log"):
    return os.path.join(base_dir,filename)