import json
from datetime import datetime

def save_dict_as_json(dict_obj, file_path):
    with open(file_path, 'w') as f:
        json.dump(dict_obj, f, indent=4)

def load_json_as_dict(file_path):
    with open(file_path, 'r', encoding="utf-8") as f:
        return json.load(f)
    
def get_current_datetime_as_str(str_format="%Y-%m-%d, %H:%M:%S"):
    now = datetime.now()
    date_time_str = now.strftime(str_format)
    return date_time_str