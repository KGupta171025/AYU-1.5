import requests
from typing import List, Dict, Any

class GoogleCustomSearch:
    def __init__(self, api_key: str, cse_id: str):
        self.api_key = api_key
        self.cse_id = cse_id
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": num_results
        }
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])
            results = []
            for item in items:
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet")
                })
            return results
        except requests.RequestException as e:
            return [{"error": str(e)}]
