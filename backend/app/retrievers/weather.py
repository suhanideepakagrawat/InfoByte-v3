import os
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

OPENWEATHER_KEY = os.environ.get("OPENWEATHER_KEY")
WEATHERAPI_KEY = os.environ.get("WEATHERAPI_KEY")

# Alias Mapping: Intercepts modern city names for backend API compatibility
CITY_ALIASES = {
    "gurugram": "gurgaon",
    "bengaluru": "bangalore",
    "prayagraj": "allahabad",
    "mysuru": "mysore",
    "thiruvananthapuram": "trivandrum"
}

def extract_location(query: str) -> str:
    """Removes common intent words to isolate the city name for the API request."""
    stopwords = {"weather", "in", "of", "for", "current", "what", "is", "the", "like", "tell", "me", "show", "it", "raining", "rain"}
    words = query.lower().split()
    clean_words = [w for w in words if w not in stopwords]
    return " ".join(clean_words).strip() if clean_words else query.strip()

def normalize_city_name(location: str) -> str:
    """Maps modern city names to standard legacy names recognized by geo-databases."""
    return CITY_ALIASES.get(location.lower(), location)

def format_weather_data(data: dict, provider: str) -> str:
    try:
        if provider == "OpenWeather":
            temp_k = data['main']['temp']
            feels_k = data['main']['feels_like']
            temp_c = round(temp_k - 273.15, 1)
            feels_c = round(feels_k - 273.15, 1)
            desc = data['weather'][0]['description'].capitalize()
            humidity = data['main']['humidity']
            wind = f"{data['wind']['speed']} m/s"
            rain = data.get('rain', {}).get('1h', 0)
            
        elif provider == "WeatherAPI":
            temp_c = data['current']['temp_c']
            feels_c = data['current']['feelslike_c']
            temp_k = round(temp_c + 273.15, 2)
            feels_k = round(feels_c + 273.15, 2)
            desc = data['current']['condition']['text']
            humidity = data['current']['humidity']
            wind = f"{data['current']['wind_kph']} kph"
            rain = data['current'].get('precip_mm', 0)
            
        return (
            f"Condition: {desc}\n"
            f"Temp (Celsius): {temp_c}°C (Feels like {feels_c}°C)\n"
            f"Temp (Kelvin): {temp_k}K (Feels like {feels_k}K)\n"
            f"Humidity: {humidity}%\n"
            f"Wind: {wind}\n"
            f"Rain: {rain}mm"
        )
    except Exception:
        return "Weather data unavailable."

def handle_weather_query(search_query: str) -> dict:
    # 1. Clean and normalize behind the scenes so the backend APIs never throw a 400/404 error
    extracted_location = extract_location(search_query)
    normalized_query = normalize_city_name(extracted_location)
    
    providers = ["WeatherAPI", "OpenWeather"]
    
    for provider in providers:
        try:
            if provider == "WeatherAPI":
                url = f"https://api.weatherapi.com/v1/current.json?key={WEATHERAPI_KEY}&q={normalized_query}"
            else:
                url = f"https://api.openweathermap.org/data/2.5/weather?q={normalized_query}&appid={OPENWEATHER_KEY}"
            
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            
            return {
                "status": "success",
                "display_payload": {
                    # 2. Always use the EXACT query entered by the user as the title heading
                    "title": search_query.strip(),
                    "main_text": format_weather_data(data, provider),
                    "source_url": None,
                    "metadata": {"provider": provider}
                },
                "system_metrics": {"latency_ms": resp.elapsed.total_seconds() * 1000}
            }
        except Exception as e:
            print(f"[DEBUG] {provider} failed for {normalized_query}: {e}")
            continue

    return {"status": "error", "display_payload": {"title": "Error", "main_text": "Weather service currently unavailable."}}