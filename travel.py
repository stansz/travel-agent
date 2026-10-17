#!/usr/bin/env python3
"""Travel Agent — unified CLI for the travel stack.

Usage:
  travel.py deals [--filter asia] [--max-price 1000]
  travel.py prices --from YVR --to BKK [--month 2026-11] [--currency CAD]
  travel.py search <query>
  travel.py flight AC123 [--date 2026-06-15]
  travel.py flight --from YVR --to BKK [--date 2026-06-15]
  travel.py hotels <city> [--checkin DATE] [--checkout DATE]
  travel.py advisory --list [--level 4]
  travel.py weather <city> [--days 7]
  travel.py pack <destination> <days> [--activities beach,hiking]
  travel.py time <country>
  travel.py plugs <country>
  travel.py emergency <country>
  travel.py fx <from_currency> <to_currency> [--amount 100]
  travel.py airport <IATA>
  travel.py routes <IATA> [--to <dest>]
  travel.py nearby <IATA>
  travel.py translate "hello" --to th
  travel.py phrases Thailand

Tools:
  deals     → YVR Deals feed (flash sales, mistake fares)
  prices    → Travelpayouts price lookup (cached, ~48h delay)
  search    → Web search for real-time prices (SearXNG)
  flight    → AirLabs + AviationStack flight status, delays, gates
  hotels    → Hotel search via web + Google Places
  advisory  → Canada travel advisories (risk levels, entry reqs, alerts)
  weather   → Weather forecast for destination (via weather skill)
  pack      → AI-generated packing list based on weather + activities
  time      → Current time and offset from Vancouver
  plugs     → Power plug types, voltage, adapter info
  emergency → Emergency numbers for the destination
  fx        → Currency conversion (live rates via Twelve Data)
  airport   → Airport info (name, ICAO, coordinates, country)
  routes    → All destinations from an airport (AirLabs)
  nearby    → Alternate airports near a city (AirLabs)
  translate → Translate text to destination language (LibreTranslate)
  phrases   → Essential travel phrases for a country (LibreTranslate)
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent.parent  # skills/travel/


def _env(name: str, default: str = "") -> str:
    """Read a setting from the environment, falling back to ~/.hermes/.env."""
    if os.environ.get(name):
        return os.environ[name]
    env_file = Path.home() / ".hermes" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip() == name and v.strip():
                    return v.strip()
    return default


def searx_json(query: str, extra: str = "&categories=general&pageno=1", timeout: int = 15) -> dict:
    """Query SearXNG (SEARXNG_URL, basic-auth aware) and return parsed JSON."""
    base = _env("SEARXNG_URL", "http://127.0.0.1:8080")
    p = urllib.parse.urlparse(base)
    netloc = p.hostname or "127.0.0.1"
    if p.port:
        netloc = f"{netloc}:{p.port}"
    url = (f"{p.scheme or 'http'}://{netloc}/search?"
           f"q={urllib.parse.quote(query)}&format=json{extra}")
    req = urllib.request.Request(url, headers={"User-Agent": "TravelAgent/1.0"})
    if p.username:
        cred = f"{urllib.parse.unquote(p.username)}:{urllib.parse.unquote(p.password or '')}"
        req.add_header("Authorization", "Basic " + base64.b64encode(cred.encode()).decode())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def run_script(rel_path: str, *args: str) -> int:
    script = SKILL_DIR / rel_path
    cmd = [sys.executable, str(script), *args]
    return subprocess.run(cmd).returncode


def cmd_deals(args):
    extra = []
    if args.filter:
        extra.extend(["--filter", args.filter])
    if args.max_price:
        extra.extend(["--max-price", str(args.max_price)])
    return run_script("yvr-deals/scripts/fetch_deals.py", *extra)


def cmd_prices(args):
    if not args.origin or not args.dest:
        sys.exit("--from and --to are required for prices")
    extra = ["--from", args.origin, "--to", args.dest, "--currency", args.currency or "CAD"]
    if args.month:
        extra.extend(["--month", args.month])
    return run_script("travelpayouts/scripts/tp.py", *extra)

def cmd_search(args):
    """Web search fallback."""
    query = " ".join(args.query)
    print(f"🔍 Search: {query}")
    print("Run this in the agent: web_search for flights/destinations")
    return 0


def cmd_hotels(args):
    """Hotel search — uses web search and Google Places."""
    city = args.city
    checkin = args.checkin or ""
    checkout = args.checkout or ""
    budget = args.budget or ""

    date_str = f" {checkin} to {checkout}" if checkin and checkout else ""
    budget_str = f" under ${budget}" if budget else ""

    print(f"🏨 Hotels in {city}{date_str}{budget_str}")
    print()
    print("The agent will search for hotels using:")
    print(f"  1. Google Places: 'hotels in {city}' — names, ratings, locations")
    print(f"  2. Web search: 'best hotels {city}{budget_str}{date_str}' — pricing, reviews")
    print(f"  3. Wikipedia: {city} — neighborhood guides")
    print()
    print(f"Ask the agent: 'Find hotels in {city}...'")
    return 0

def cmd_flight(args):
    """Flight status — tries AirLabs first (1k req/mo), falls back to AviationStack."""
    extra = []
    if args.flight_number:
        extra.append(args.flight_number)
    if args.origin:
        extra.extend(["--from", args.origin])
    if args.dest:
        extra.extend(["--to", args.dest])
    if args.date:
        extra.extend(["--date", args.date])
    if args.limit:
        extra.extend(["--limit", str(args.limit)])
    if args.sched:
        extra.append("--sched")

    # Try AirLabs first (10x more quota)
    rc = run_script("airlabs/scripts/airlabs.py", *extra)
    if rc == 0:
        return rc

    # Fall back to AviationStack
    return run_script("aviationstack/scripts/flights.py", *extra)


def cmd_advisory(args):
    extra = []
    if args.advisory_list:
        extra.append("--list")
    if args.level:
        extra.extend(["--level", str(args.level)])
    if args.search:
        extra.extend(["--search", args.search])
    if args.refresh:
        extra.append("--refresh")
    if args.country:
        extra.append(args.country)
    return run_script("travel-advisories/scripts/advisory.py", *extra)


def cmd_weather(args):
    print(f"🌤 Weather for {args.destination}")
    print(f"\nUse the weather tool for: {args.destination}")
    print("The agent will fetch current conditions + forecast automatically.")
    return 0


def cmd_pack(args):
    destination = args.destination
    days = args.days
    activities = args.activities or "general sightseeing"
    print(f"🎒 Packing list for {destination} — {days} days ({activities})")
    print()
    print("The agent generates this based on:")
    print(f"  1. Weather: current forecast for {destination}")
    print(f"  2. Duration: {days} days")
    print(f"  3. Activities: {activities}")
    print()
    print("Ask the agent: 'Generate a packing list for X days in Y with Z activities'")
    return 0


def cmd_time(args):
    return run_script("travel-utils/scripts/utils.py", args.country, "--time")


def cmd_plugs(args):
    return run_script("travel-utils/scripts/utils.py", args.country, "--plugs")


def cmd_emergency(args):
    return run_script("travel-utils/scripts/utils.py", args.country, "--emergency")


def cmd_fx(args):
    from_cur = args.from_currency.upper()
    to_cur = args.to_currency.upper()
    amount = args.amount or 1.0

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "utils", SKILL_DIR / "travel-utils/scripts/utils.py"
    )
    utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(utils)
    utils.cmd_fx(from_cur, to_cur, amount)
    return 0


def cmd_airport(args):
    return run_script("airlabs/scripts/airlabs_extras.py", "airport", args.iata)


def cmd_routes(args):
    extra = ["routes", args.iata]
    if args.to_dest:
        extra.extend(["--to", args.to_dest])
    if args.limit:
        extra.extend(["--limit", str(args.limit)])
    return run_script("airlabs/scripts/airlabs_extras.py", *extra)


def cmd_nearby(args):
    extra = ["nearby", args.iata]
    if args.distance:
        extra.extend(["--distance", str(args.distance)])
    return run_script("airlabs/scripts/airlabs_extras.py", *extra)


def cmd_translate(args):
    extra = ["translate", args.text]
    if args.source:
        extra.extend(["--from", args.source])
    if args.target:
        extra.extend(["--to", args.target])
    return run_script("libretranslate/scripts/translate.py", *extra)


def cmd_phrases(args):
    return run_script("libretranslate/scripts/translate.py", "phrases", args.country)


def cmd_reddit(args):
    """Search Reddit travel subreddits via web search (SearXNG)."""
    import json
    import urllib.request
    import urllib.parse

    query = " ".join(args.query)
    subreddits = args.subreddits or "travel+solotravel+travelhacks"
    limit = min(args.limit or 8, 15)

    # Build a site:reddit.com search query
    sub_list = [f"r/{s}" for s in subreddits.split("+")]
    site_query = " OR ".join([f"site:reddit.com/{s}" for s in sub_list])
    search_query = f"{site_query} {query}"

    try:
        data = searx_json(search_query)
    except Exception as e:
        print(f"Search failed: {e}")
        return 1

    results = data.get("results", [])[:limit]
    if not results:
        print(f"No results found for '{query}' in r/{subreddits}.")
        return 0

    print(f"🔍 r/{subreddits} — '{query}' ({len(results)} results)\n")
    for i, r in enumerate(results, 1):
        title = r.get("title", "").replace(" : ", ": ")
        url = r.get("url", "")
        snippet = r.get("content", "")[:250]
        # Try to extract score from snippet if present
        print(f"{i}. **{title}**")
        print(f"   🔗 {url}")
        if snippet:
            print(f"   {snippet}{'...' if len(snippet) > 200 else ''}")
        print()
    return 0


def cmd_wikivoyage(args):
    """Fetch a WikiVoyage destination guide."""
    import json
    import urllib.request
    import urllib.parse

    destination = args.destination
    encoded = urllib.parse.quote(destination)

    # Search for the page first
    search_url = f"https://en.wikivoyage.org/w/api.php?action=opensearch&search={encoded}&limit=1&format=json"
    try:
        req = urllib.request.Request(search_url, headers={"User-Agent": "TravelAgent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            search_data = json.loads(resp.read())
    except Exception as e:
        print(f"WikiVoyage search failed: {e}")
        return 1

    if not search_data[1]:
        print(f"❌ No WikiVoyage article found for '{destination}'. Try a more specific name.")
        return 1

    page_title = search_data[1][0]
    page_url = search_data[3][0]

    # Fetch the page extract
    extract_url = (
        f"https://en.wikivoyage.org/w/api.php?action=query&titles={urllib.parse.quote(page_title)}"
        f"&prop=extracts&exintro=1&explaintext=1&format=json"
    )
    try:
        req = urllib.request.Request(extract_url, headers={"User-Agent": "TravelAgent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            extract_data = json.loads(resp.read())
    except Exception as e:
        print(f"WikiVoyage extract failed: {e}")
        return 1

    pages = extract_data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if pid == "-1":
            continue
        extract = page.get("extract", "No summary available.")
        # Truncate to ~2000 chars
        if len(extract) > 2000:
            extract = extract[:2000] + "..."
        print(f"📖 **{page_title}** — WikiVoyage\n")
        print(extract)
        print(f"\n🔗 Full article: {page_url}")
    return 0


def cmd_cruise(args):
    """Search for cruise deals available to Canadians. Uses web search across Canadian travel sites + r/Cruise."""
    import json
    import urllib.request
    import urllib.parse

    query = args.query or ""
    limit = min(args.limit or 10, 20)

    print("🚢 **Cruise Deals for Canadians**\n")

    # Build targeted search queries for Canadian cruises
    base_queries = [
        "cruise deals Canada 2026 CAD",
        "cheap cruises for Canadians",
        "best cruise deals Canada book now",
    ]
    if query:
        base_queries.insert(0, f"{query} cruise Canada deals")

    # Also note popular departure ports Canadians use
    print("📌 Canadians commonly cruise from: Vancouver, Seattle, Fort Lauderdale, Miami, Barcelona, Rome, Southampton")
    print()

    all_results = []
    for q in base_queries[:2]:  # Run top 2 queries
        try:
            data = searx_json(q)
            results = data.get("results", [])
            # Prioritize Canadian/booking sites
            ca_sites = ("expedia.ca", "cruisecritic", "costcotravel", "redtag.ca", "vacationstogo",
                        "tripcentral", "selloffvacations", "itravel2000", "flightcentre.ca")
            for r in results:
                url = r.get("url", "")
                score = sum(1 for s in ca_sites if s in url.lower())
                all_results.append((score, r))
        except Exception:
            continue

    # Deduplicate by URL and sort by Canadian-relevance
    seen = set()
    unique = []
    for score, r in sorted(all_results, key=lambda x: (-x[0], x[1].get("title", ""))):
        url = r.get("url", "")
        if url not in seen:
            seen.add(url)
            unique.append(r)

    if unique:
        print(f"🔍 **Deals & Offers** ({len(unique[:limit])} results)\n")
        for i, r in enumerate(unique[:limit], 1):
            title = r.get("title", "").replace(" : ", ": ")
            url = r.get("url", "")
            snippet = r.get("content", "")[:200]
            print(f"{i}. **{title}**")
            print(f"   🔗 {url}")
            if snippet:
                print(f"   {snippet}{'...' if len(snippet) > 180 else ''}")
            print()

        print("💡 **Tips for Canadian cruisers:**")
        print("   • Book in CAD when possible — avoid USD conversion fees")
        print("   • Check if gratuities, drinks, and Wi-Fi are included")
        print("   • Fly to US departure ports (Seattle, Miami) for more options & lower fares")
        print("   • Use a Canadian travel credit card with no FX fees")
    else:
        print("No cruise deals found right now. Try:")
        print("   • Expedia.ca/cruises  • CostcoTravel.ca  • CruiseCritic.com")
        print("   • RedTag.ca  • SellOffVacations.com  • Vacationstogo.com")
        print()
        print("Also try: `travel.py cruise -q \"Alaska\"` or `travel.py cruise -q \"Caribbean\"`")

    return 0


def cmd_recommend(args):
    """Recommend trips based on style, season, budget — searches web via SearXNG."""
    import json
    import urllib.request
    import urllib.parse

    style = args.style or ""
    budget = f"under ${args.budget}" if args.budget else "affordable"
    month = args.month or ""

    queries = []
    base = "best places to visit"
    if month:
        queries.append(f"{base} {month} {budget}")
        queries.append(f"where to travel {month} ideas")
    if style:
        queries.append(f"best {style} destinations {budget}")
        queries.append(f"{style} trip ideas {month}")

    if not queries:
        queries = [f"{base} 2026 {budget}", f"underrated travel destinations 2026"]

    search_query = f"site:reddit.com/r/travel ({' OR '.join(queries[:2])})"
    limit = min(args.limit or 6, 15)

    try:
        data = searx_json(search_query)
    except Exception as e:
        print(f"Search failed: {e}")
        return 1

    results = data.get("results", [])
    if not results:
        print("No recommendations found. Try a different style or season.")
        return 0

    print("🧳 **Trip Recommendations**\n")
    if style:
        print(f"Style: {style}")
    if month:
        print(f"Season: {month}")
    if args.budget:
        print(f"Budget: ${args.budget} CAD")
    print()

    # Extract destinations from titles
    known_destinations = {"Japan", "Thailand", "Italy", "Mexico", "Spain", "France", "Greece",
        "Peru", "Vietnam", "Korea", "Indonesia", "Portugal", "Colombia", "Morocco", "Turkey",
        "Iceland", "Croatia", "Norway", "Australia", "Brazil", "India", "Costa Rica", "New Zealand"}
    seen = set()
    destinations = []

    for r in results:
        title = r.get("title", "").replace(" : ", ": ")
        url = r.get("url", "")
        for dest in known_destinations:
            if dest.lower() in title.lower() and dest.lower() not in seen:
                seen.add(dest.lower())
                destinations.append((dest, title, url))

    if destinations:
        print(f"🎯 Destinations mentioned ({len(destinations)} found):\n")
        for dest, title, url in destinations[:10]:
            print(f"  ✈️ **{dest}** — from: _{title}_")
        print()
        print("💡 Ask me: 'Tell me more about [destination]'")
        print("   I can check flights, weather, advisories, and more!")
    else:
        print("📋 Top posts:\n")
        for i, r in enumerate(results[:limit], 1):
            print(f"{i}. **{r.get('title', '')}**")
            print(f"   🔗 {r.get('url', '')}")
            print()

    return 0


def main():
    parser = argparse.ArgumentParser(description="Travel Agent CLI")
    sub = parser.add_subparsers(dest="command")

    p_deals = sub.add_parser("deals", help="YVR Deals feed")
    p_deals.add_argument("--filter", help="Category filter (e.g. asia, thailand)")
    p_deals.add_argument("--max-price", type=int, help="Max price in CAD")

    p_prices = sub.add_parser("prices", help="Flight price lookup (Travelpayouts)")
    p_prices.add_argument("--from", dest="origin", required=True, help="Origin IATA (e.g. YVR)")
    p_prices.add_argument("--to", dest="dest", required=True, help="Destination IATA (e.g. BKK)")
    p_prices.add_argument("--month", help="Month for price calendar (YYYY-MM)")
    p_prices.add_argument("--currency", default="CAD", help="Currency code")

    p_search = sub.add_parser("search", help="Web search fallback (SearXNG)")
    p_search.add_argument("query", nargs="+", help="Search query")

    p_flight = sub.add_parser("flight", help="Flight status (AirLabs + AviationStack)")
    p_flight.add_argument("flight_number", nargs="?", help="Flight number (e.g. AC123)")
    p_flight.add_argument("--from", dest="origin", help="Origin airport IATA")
    p_flight.add_argument("--to", dest="dest", help="Destination airport IATA")
    p_flight.add_argument("--date", "-d", help="Flight date (YYYY-MM-DD)")
    p_flight.add_argument("--sched", action="store_true", help="Show schedules with gates (vs live ADS-B)")
    p_flight.add_argument("--limit", type=int, default=8, help="Max results")

    p_hotels = sub.add_parser("hotels", help="Hotel search")
    p_hotels.add_argument("city", help="City or destination")
    p_hotels.add_argument("--checkin", help="Check-in date (YYYY-MM-DD)")
    p_hotels.add_argument("--checkout", help="Check-out date (YYYY-MM-DD)")
    p_hotels.add_argument("--budget", type=int, help="Max nightly budget in CAD")

    p_adv = sub.add_parser("advisory", help="Canada travel advisories")
    p_adv.add_argument("country", nargs="?", help="Country name or ISO code")
    p_adv.add_argument("--list", dest="advisory_list", action="store_true", help="List all countries")
    p_adv.add_argument("--level", type=int, choices=[1, 2, 3, 4], help="Filter by risk level")
    p_adv.add_argument("--search", "-s", help="Fuzzy search countries")
    p_adv.add_argument("--refresh", action="store_true", help="Force refresh from source")

    p_weather = sub.add_parser("weather", help="Weather at destination")
    p_weather.add_argument("destination", help="City or location")
    p_weather.add_argument("--days", type=int, default=7, help="Forecast days (default: 7)")

    p_pack = sub.add_parser("pack", help="Generate a packing list")
    p_pack.add_argument("destination", help="Destination city/country")
    p_pack.add_argument("days", type=int, help="Trip duration in days")
    p_pack.add_argument("--activities", "-a", help="Activities (comma-separated)")

    p_time = sub.add_parser("time", help="Current time at destination")
    p_time.add_argument("country", help="Country name (e.g. Thailand, Japan)")

    p_plugs = sub.add_parser("plugs", help="Power plugs and voltage info")
    p_plugs.add_argument("country", help="Country name (e.g. Thailand, Japan)")

    p_emerg = sub.add_parser("emergency", help="Emergency numbers at destination")
    p_emerg.add_argument("country", help="Country name (e.g. Thailand, Japan)")

    p_fx = sub.add_parser("fx", help="Currency conversion")
    p_fx.add_argument("from_currency", help="From currency (e.g. CAD)")
    p_fx.add_argument("to_currency", help="To currency (e.g. THB)")
    p_fx.add_argument("--amount", type=float, default=1.0, help="Amount to convert")

    p_airport = sub.add_parser("airport", help="Airport info (AirLabs)")
    p_airport.add_argument("iata", help="Airport IATA code (e.g. BKK)")

    p_routes = sub.add_parser("routes", help="Destinations from an airport (AirLabs)")
    p_routes.add_argument("iata", help="Origin airport IATA (e.g. YVR)")
    p_routes.add_argument("--to", dest="to_dest", help="Filter by destination IATA")
    p_routes.add_argument("--limit", type=int, default=20, help="Max results")

    p_nearby = sub.add_parser("nearby", help="Nearby airports (AirLabs)")
    p_nearby.add_argument("iata", help="Airport IATA code (e.g. BKK)")
    p_nearby.add_argument("--distance", type=int, default=100, help="Radius in km")

    p_trans = sub.add_parser("translate", help="Translate text (LibreTranslate)")
    p_trans.add_argument("text", help="Text to translate")
    p_trans.add_argument("--from", dest="source", default="auto", help="Source language (auto-detect)")
    p_trans.add_argument("--to", dest="target", default="en", help="Target language (e.g. th, ja)")

    p_phrases = sub.add_parser("phrases", help="Travel phrases for a country")
    p_phrases.add_argument("country", help="Country name or language code")

    p_reddit = sub.add_parser("reddit", help="Search Reddit travel subreddits")
    p_reddit.add_argument("query", nargs="+", help="Search query (e.g. 'Kyoto itinerary', 'solo Europe')")
    p_reddit.add_argument("--subreddits", "-r", help="Subreddits (default: travel+solotravel+travelhacks)")
    p_reddit.add_argument("--sort", choices=["relevance", "hot", "new", "top", "comments"], default="relevance")
    p_reddit.add_argument("--time", "-t", choices=["hour", "day", "week", "month", "year", "all"], default="year")
    p_reddit.add_argument("--limit", "-n", type=int, default=8)

    p_wikivoyage = sub.add_parser("wikivoyage", help="Fetch WikiVoyage destination guide")
    p_wikivoyage.add_argument("destination", help="Destination (e.g. 'Bangkok', 'Kyoto', 'Paris')")

    p_cruise = sub.add_parser("cruise", help="Cruise deals & Canadian departure info")
    p_cruise.add_argument("--query", "-q", help="Search query (e.g. 'Alaska', 'Caribbean')")
    p_cruise.add_argument("--limit", "-n", type=int, default=10)

    p_recommend = sub.add_parser("recommend", help="Get trip recommendations")
    p_recommend.add_argument("--style", "-s", help="Trip style (e.g. beach, adventure, food, culture, budget)")
    p_recommend.add_argument("--month", "-m", help="Travel month (e.g. June, December)")
    p_recommend.add_argument("--budget", "-b", type=int, help="Budget in CAD")
    p_recommend.add_argument("--limit", "-n", type=int, default=6)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "deals": cmd_deals, "prices": cmd_prices, "search": cmd_search,
        "flight": cmd_flight, "hotels": cmd_hotels, "advisory": cmd_advisory,
        "weather": cmd_weather, "pack": cmd_pack,
        "time": cmd_time, "plugs": cmd_plugs,
        "emergency": cmd_emergency, "fx": cmd_fx,
        "airport": cmd_airport, "routes": cmd_routes, "nearby": cmd_nearby,
        "translate": cmd_translate, "phrases": cmd_phrases,
        "reddit": cmd_reddit, "wikivoyage": cmd_wikivoyage,
        "cruise": cmd_cruise, "recommend": cmd_recommend,
    }
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
