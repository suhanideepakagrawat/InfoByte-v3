import os
from dotenv import load_dotenv

# Force load from the current directory
load_dotenv(dotenv_path='.env')

keys = ["NEWSAPI_KEY", "TMDB_KEY", "OPENWEATHER_KEY", "WEATHERAPI_KEY"]
for k in keys:
    val = os.environ.get(k)
    print(f"{k}: {'Loaded (starts with ' + val[:5] + '...)' if val else 'NOT FOUND'}")