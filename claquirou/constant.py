import os

FOLDER = os.path.dirname(__file__)
PARAMS = os.path.join(os.path.dirname(FOLDER), "token.ini")

EN_TIPS = os.path.join(FOLDER, "en/tips.json")
FR_TIPS = os.path.join(FOLDER, "fr/tips.json")

LOG_FILE = os.path.join(os.path.dirname(FOLDER), ".log/file.log")
