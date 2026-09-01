# tools/gym_finder.py
import math
import requests
from typing import Optional, List, Dict, Any, Tuple
from langchain_core.prompts import ChatPromptTemplate
from graph.state import AgentState
from models.llm import get_llm
from memory.session_memory import format_chat_history
from config.settings import settings


'''
                START
                  │
                  ▼
        Check Geoapify API Key Exists
                  │
                  ▼
       Read Combined Location Field
                  │
                  ▼
     Build Location Candidates from String
                  │
                  ▼
    "Kharar, Mohali" → Full / Part Fallbacks
                  │
                  ▼
     Try Geocoding Candidate Locations
                  │
                  ▼
      Get Latitude / Longitude from Geoapify
                  │
                  ▼
      Search Nearby Gyms with Multiple Radii
                  │
                  ▼
      5 km → 10 km → 15 km fallback
                  │
                  ▼
        Clean + Deduplicate Results
                  │
                  ▼
      Skip only if no valid gym name found
                  │
                  ▼
          Sort by Nearest Distance
                  │
                  ▼
          Build Final LLM Response
                  │
                  ▼
            Return formatted gym_data
                  │
                  ▼
                 END
'''


class GymFinderTool:
    """
    Finds nearby gyms using Geoapify Geocoding + Places API
    based on a single combined location field.
    """

    GEOCODING_URL = "https://api.geoapify.com/v1/geocode/search"
    PLACES_URL = "https://api.geoapify.com/v2/places"

    # Dynamic search fallback radii
    SEARCH_RADII_METERS = [5000, 10000, 15000]

    MAX_RESULTS = 5

    @staticmethod
    def _safe_clean_text(value: Any) -> str:
        """
        Safely converts any value to clean string.
        """
        if value is None:
            return ""

        if isinstance(value, list):
            value = " ".join(str(item) for item in value if item)

        return str(value).strip()

    @staticmethod
    def _build_location_candidates(state: AgentState) -> List[str]:
        """
        Builds location candidates from a single combined location field.

        Example:
        location = "Kharar, Mohali"

        Candidates:
        1. "Kharar, Mohali"
        2. "Kharar"
        3. "Mohali"
        """
        profile = state["user_profile"]
        raw_location = GymFinderTool._safe_clean_text(getattr(profile, "location", None))

        if not raw_location:
            return []

        candidates = []
        seen = set()

        def add_candidate(value: str):
            cleaned = value.strip()
            if cleaned and cleaned.lower() not in seen:
                candidates.append(cleaned)
                seen.add(cleaned.lower())

        # 1. Full location string first
        add_candidate(raw_location)

        # 2. Split by commas and try each meaningful part
        parts = [part.strip() for part in raw_location.split(",") if part.strip()]

        if len(parts) >= 2:
            # First part usually area/locality
            add_candidate(parts[0])

            # Last part usually city/broader area
            add_candidate(parts[-1])

            # If 3+ parts exist, also try broader joined fallback
            # Example: "Sector 70, Mohali, Punjab"
            # fallback: "Mohali, Punjab"
            if len(parts) >= 3:
                add_candidate(", ".join(parts[1:]))

        return candidates

    @staticmethod
    def _get_coordinates(location_text: str) -> Optional[Dict[str, Any]]:
        """
        Uses Geoapify Geocoding API to convert a location string
        into latitude and longitude.
        """
        try:
            response = requests.get(
                GymFinderTool.GEOCODING_URL,
                params={
                    "text": location_text,
                    "apiKey": settings.GEOAPIFY_API_KEY,
                    "limit": 1,
                    "format": "json"
                },
                timeout=20
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                return None

            first_result = results[0]
            lat = first_result.get("lat")
            lon = first_result.get("lon")

            if lat is None or lon is None:
                return None

            return {
                "lat": float(lat),
                "lon": float(lon),
                "formatted": first_result.get("formatted", location_text)
            }

        except Exception:
            return None

    @staticmethod
    def _search_nearby_gyms(lat: float, lon: float, radius_meters: int) -> List[Dict[str, Any]]:
        """
        Uses Geoapify Places API to search nearby gyms.
        """
        try:
            response = requests.get(
                GymFinderTool.PLACES_URL,
                params={
                    "categories": "sport.fitness",
                    "filter": f"circle:{lon},{lat},{radius_meters}",
                    "limit": 50,
                    "apiKey": settings.GEOAPIFY_API_KEY
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            return data.get("features", [])

        except Exception:
            return []

    @staticmethod
    def _calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculates real-world distance in kilometers using Haversine formula.
        """
        earth_radius_km = 6371.0

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(math.radians(lat1)) *
            math.cos(math.radians(lat2)) *
            math.sin(dlon / 2) ** 2
        )

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return earth_radius_km * c

    @staticmethod
    def _extract_gym_name(properties: Dict[str, Any]) -> Optional[str]:
        """
        Extracts gym name using multiple fallback fields.

        Priority:
        1. properties.name
        2. properties.datasource.raw.name
        3. properties.datasource.raw.brand
        4. properties.datasource.raw.operator

        Returns None only if no usable name is found.
        """
        direct_name = GymFinderTool._safe_clean_text(properties.get("name"))
        if direct_name:
            return direct_name

        raw = properties.get("datasource", {}).get("raw", {})

        raw_name = GymFinderTool._safe_clean_text(raw.get("name"))
        if raw_name:
            return raw_name

        raw_brand = GymFinderTool._safe_clean_text(raw.get("brand"))
        if raw_brand:
            return raw_brand

        raw_operator = GymFinderTool._safe_clean_text(raw.get("operator"))
        if raw_operator:
            return raw_operator

        return None

    @staticmethod
    def _build_address(properties: Dict[str, Any]) -> str:
        """
        Builds readable address string from Geoapify properties.
        """
        formatted = GymFinderTool._safe_clean_text(properties.get("formatted"))
        if formatted:
            return formatted

        address_line1 = GymFinderTool._safe_clean_text(properties.get("address_line1"))
        address_line2 = GymFinderTool._safe_clean_text(properties.get("address_line2"))

        if address_line1 and address_line2:
            return f"{address_line1}, {address_line2}"
        if address_line1:
            return address_line1
        if address_line2:
            return address_line2

        address_parts = []
        for key in ["street", "suburb", "district", "city", "state", "country"]:
            value = GymFinderTool._safe_clean_text(properties.get(key))
            if value:
                address_parts.append(value)

        return ", ".join(address_parts) if address_parts else "Address not available"

    @staticmethod
    def _clean_and_sort_results(
        raw_results: List[Dict[str, Any]],
        user_lat: float,
        user_lon: float
    ) -> List[Dict[str, Any]]:
        """
        Converts raw Geoapify results into clean structured gym entries.

        - Extract usable name with multiple fallbacks
        - Skip only truly unnamed results
        - Deduplicate by name + address
        - Sort by nearest distance
        """
        cleaned_results = []
        seen_entries = set()

        for feature in raw_results:
            properties = feature.get("properties", {})
            geometry = feature.get("geometry", {})

            coordinates = geometry.get("coordinates", [])
            if len(coordinates) < 2:
                continue

            # GeoJSON format: [longitude, latitude]
            gym_lon, gym_lat = coordinates[0], coordinates[1]

            gym_name = GymFinderTool._extract_gym_name(properties)
            if not gym_name:
                continue

            address = GymFinderTool._build_address(properties)

            distance_km = GymFinderTool._calculate_distance_km(
                user_lat, user_lon, gym_lat, gym_lon
            )

            unique_key = (gym_name.lower(), address.lower())
            if unique_key in seen_entries:
                continue

            seen_entries.add(unique_key)

            cleaned_results.append({
                "name": gym_name,
                "address": address,
                "distance_km": round(distance_km, 2)
            })

        cleaned_results.sort(key=lambda gym: gym["distance_km"])
        return cleaned_results[:GymFinderTool.MAX_RESULTS]

    @staticmethod
    def _format_gym_list_for_prompt(gyms: List[Dict[str, Any]]) -> str:
        """
        Converts gym list into prompt-friendly numbered string.
        """
        if not gyms:
            return "No gyms found."

        lines = []
        for index, gym in enumerate(gyms, start=1):
            lines.append(
                f"{index}. {gym['name']} | Distance: {gym['distance_km']} km | Address: {gym['address']}"
            )

        return "\n".join(lines)

    @staticmethod
    def find_gyms(state: AgentState) -> dict:
        """
        Main gym finder execution flow.
        Tries multiple location candidates and multiple search radii.
        """
        profile = state["user_profile"]
        query = state.get("user_query") or profile.query
        chat_history = format_chat_history(state.get("chat_history", []))

        # --------------------------------------------------
        # Check API key configuration
        # --------------------------------------------------
        if not settings.GEOAPIFY_API_KEY:
            return {
                "gym_data": (
                    "Gym search service is not configured properly because Geoapify API key is missing."
                )
            }

        # --------------------------------------------------
        # Build location candidates from single location field
        # Full input → split fallbacks
        # --------------------------------------------------
        location_candidates = GymFinderTool._build_location_candidates(state)

        if not location_candidates:
            return {
                "gym_data": (
                    "Please share your location so I can find nearby gyms for you. "
                    "For example: location='Kharar, Mohali'."
                )
            }

        selected_location_label = None
        selected_geocode_display = None
        selected_gyms = []

        # --------------------------------------------------
        # Multi-step fallback strategy
        # 1. Try full location string
        # 2. Try split location parts
        # For each candidate:
        #    5 km → 10 km → 15 km
        # --------------------------------------------------
        for location_text in location_candidates:
            geocode_result = GymFinderTool._get_coordinates(location_text)

            if not geocode_result:
                continue

            user_lat = geocode_result["lat"]
            user_lon = geocode_result["lon"]
            selected_geocode_display = geocode_result.get("formatted", location_text)

            for radius in GymFinderTool.SEARCH_RADII_METERS:
                raw_results = GymFinderTool._search_nearby_gyms(user_lat, user_lon, radius)
                nearby_gyms = GymFinderTool._clean_and_sort_results(raw_results, user_lat, user_lon)

                if nearby_gyms:
                    selected_location_label = location_text
                    selected_gyms = nearby_gyms
                    break

            if selected_gyms:
                break

        # --------------------------------------------------
        # If no gyms found after all fallbacks
        # --------------------------------------------------
        if not selected_gyms:
            tried_locations = ", ".join(location_candidates)
            return {
                "gym_data": (
                    f"I could not find named nearby gyms for the provided location input. "
                    f"Tried these location variants: {tried_locations}. "
                    f"Please try a broader city name or a more specific locality."
                )
            }

        # --------------------------------------------------
        # Build final user-friendly response using LLM
        # --------------------------------------------------
        llm = get_llm(temperature=0.2, purpose="gym")

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are a fitness environment and gym guidance assistant.\n\n"
                "You are given REAL nearby gym search results already fetched from Geoapify Places API.\n"
                "Your job is to present them clearly and briefly.\n\n"
                "Rules:\n"
                "- Do NOT invent gym names.\n"
                "- Use only the provided gym results.\n"
                "- Mention distance and address.\n"
                "- If the user has limited time, briefly mention that nearer gyms are more practical.\n"
                "- Do NOT generate workout plans or diet plans.\n"
                "- Keep the response practical, clean, and helpful."
            )),
            ("user", (
                "Recent Conversation History:\n{history}\n\n"
                "Current User Message:\n{query}\n\n"
                "Resolved Search Location:\n{resolved_location}\n\n"
                "Nearby Gyms Found:\n{gym_results}\n\n"
                "User Profile:\n"
                "- Age: {age}\n"
                "- Gender: {gender}\n"
                "- Weight: {weight} kg\n"
                "- Height: {height} cm\n"
                "- Activity Level: {activity_level}"
            ))
        ])

        chain = prompt | llm
        response = chain.invoke({
            "history": chat_history,
            "query": query,
            "resolved_location": selected_geocode_display or selected_location_label or "Unknown Location",
            "gym_results": GymFinderTool._format_gym_list_for_prompt(selected_gyms),
            "age": profile.age,
            "gender": profile.gender,
            "weight": profile.weight_kg,
            "height": profile.height_cm,
            "activity_level": profile.activity_level
        })

        return {"gym_data": response.content.strip()}