"""Delhi crash black spots — official published lists, geocoded.

Sources (all public, no key):
1. Delhi Traffic Police, "Delhi Crash Report 2021" — Table 6.28 lists all 87
   crash-prone zones (>=3 fatal or >=10 total crashes within a 500m diameter
   in calendar 2021) with simple/fatal/total counts; Table 6.25 top-10
   "blackspots" adds persons killed; Tables 6.33-6.38 give sub-type zones
   (pedestrian / two-wheeler / HTV / hit-and-run / day / night).
   traffic.delhipolice.gov.in/sites/default/files/uploads/2021/
   Delhi-Crash-Report-Final-2021.pdf
2. IIT-Delhi TRiPC + Delhi Transport Dept + Vital Strategies, "Delhi Road
   Safety Report: Data to Action" (2019-2021 crashes) — district concise
   reports at tripc.iitd.ac.in/assets/training_material/<District> Concise.pdf
   list district high-risk locations with fatal-crash and death counts; the
   audited sites carry exact DMS coordinates (Mayapuri Chowk, Moolchand,
   Motibagh, Metro Store Seelampur, Sector 7-9 Dwarka) — those are used
   verbatim (coord="official").
3. Delhi Traffic Police annual top-10 black-spot lists for 2022/2023/2024 as
   published in the press (Indian Express Dec-2023, NDTV Oct-2024,
   TOI Feb-2025) — folded into each zone's `top10` list when named.

Coordinates: TRiPC-published DMS where available (coord="official"), else
OSM geocoding of the named junction/locality via Photon/Nominatim
(coord="osm"), else a hand-verified junction placement on the named road
(coord="curated"). DTP defines a crash-prone zone as a 500m-diameter
circle, so junction-centre placement is the intended granularity.
"""
import math

# Fields: name, road/area, lat, lon, simple_2021, fatal_2021, total_2021,
# killed_2021 (top-10 table only, else None), flags (DTP 2021 subtype zones:
# n=night p=pedestrian w=two-wheeler h=hit-and-run d=day v=HTV),
# deaths_3y (TRiPC 2019-21, else None), top10 (years the spot made the
# DTP top-10), coord, coord_note.
S = [
    # ---- DTP Crash Report 2021, Table 6.28 — all 87 crash-prone zones ----
    ("Bhalswa Chowk", "Outer Ring Road", 28.7377, 77.1634, 3, 8, 11, 8, "npwhdn", None, [2021, 2022, 2023, 2024], "osm", "Bhalswa Flyover node, Outer Ring Rd"),
    ("Mukarba Chowk", "Outer Ring Road", 28.7349, 77.1555, 11, 7, 18, 7, "npwhdn", 19, [2021, 2022, 2023], "osm", "Mukarba Chowk junction node"),
    ("Punjabi Bagh Chowk", "Ring Road", 28.6740, 77.1399, 11, 7, 18, 7, "npwhn", 12, [2021, 2022], "osm", "Punjabi Bagh Chowk junction"),
    ("Zakhira Flyover", "New Rohtak Road", 28.6655, 77.1738, 10, 6, 16, 6, "whdn", None, [2021], "osm", "Zakhira Flyover"),
    ("Libaspur Bus Stand", "GT Karnal Road", 28.7534, 77.1430, 10, 6, 16, 6, "whvn", None, [2021, 2023, 2024], "osm", "Libaspur locality node, GT Karnal side"),
    ("Mukundpur Chowk", "Outer Ring Road", 28.7337, 77.1834, 7, 6, 13, 6, "d", None, [2021, 2020], "osm", "Hanuman Chowk, Mukundpur junction"),
    ("Moti Bagh Flyover", "Ring Road", 28.5804, 77.1751, 7, 5, 12, 5, "n", None, [2021], "osm", "Moti Bagh Flyover"),
    ("Nangli Poona", "GT Karnal Road", 28.7732, 77.1433, 4, 5, 9, 5, "phn", None, [2021], "osm", "Nangli Poona locality"),
    ("Siraspur", "GT Karnal Road", 28.7581, 77.1298, 2, 5, 7, 5, "phd", None, [2021], "osm", "Siraspur village node"),
    ("Shastri Park / IT Park", "Grand Trunk Road", 28.6684, 77.2505, 21, 4, 25, 4, "phdn", None, [2021], "osm", "Shastri Park junction"),
    ("Majnu Ka Tila", "Outer Ring Road", 28.6987, 77.2260, 10, 4, 14, None, "", 16, [2020], "osm", "Majnu Ka Tila node"),
    ("Metro Station Haider Pur", "Haiderpur–Badli", 28.7299, 77.1496, 9, 4, 13, None, "wh", None, [], "osm", "Haiderpur Badli Mor metro"),
    ("Swaroop Nagar", "GT Karnal Road", 28.7596, 77.1517, 9, 4, 13, None, "n", None, [], "osm", "Swaroop Nagar node"),
    ("Seelampur T Point", "Grand Trunk Road", 28.6713, 77.2690, 8, 4, 12, None, "", 12, [], "official", "TRiPC DMS — Metro Store Seelampur Intersection 28°40'16.55\"N 77°16'8.57\"E"),
    ("Rama Road Crossing", "Najafgarh Road", 28.6607, 77.1511, 6, 4, 10, None, "whd", None, [], "osm", "Rama Road crossing"),
    ("Metro Station Madipur", "Rohtak Road", 28.6765, 77.1194, 5, 4, 9, None, "d", None, [], "osm", "Madipur station"),
    ("RML Hospital", "Baba Kharak Singh Marg", 28.6227, 77.1965, 5, 4, 9, None, "pn", None, [], "osm", "RML Hospital node"),
    ("Wazirabad", "Outer Ring Road", 28.7298, 77.2213, 5, 4, 9, None, "w", None, [2024], "osm", "Wazirabad locality node"),
    ("Maya Puri Chowk", "Ring Road / Mahatma Gandhi Marg", 28.6374, 77.1300, 5, 4, 9, None, "whvn", 10, [2021, 2022], "official", "TRiPC DMS 28°38'14.68\"N 77°7'48.12\"E"),
    ("Mangolpuri Flyover", "Outer Ring Road", 28.6994, 77.1230, 5, 4, 9, None, "w", None, [], "osm", "Mangolpuri Flyover"),
    ("Karkari More", "Road 68 / GT Road", 28.6472, 77.2961, 5, 4, 9, None, "whn", None, [], "osm", "Karkari Mor Flyover"),
    ("Jharera Village", "Ring Road west / Inder Puri", 28.6271, 77.1437, 4, 4, 8, None, "n", None, [], "osm", "Delhi Inderpuri node (Jharera adjacent)"),
    ("Haider Pur", "Outer Ring Road north", 28.7299, 77.1491, 4, 4, 8, None, "ph", None, [], "osm", "Haiderpur Badli Mor"),
    ("Burari Chowk", "Burari Road", 28.7536, 77.2017, 4, 4, 8, None, "wn", 12, [2020, 2023], "curated", "Burari centre; chowk on Burari Rd corridor"),
    ("Gagan Cinema", "Wazirabad Road, Nand Nagri", 28.6957, 77.3154, 4, 4, 8, None, "", None, [], "osm", "Gagan Cinema node"),
    ("Okhla More", "Mathura Road", 28.5637, 77.2891, 3, 4, 7, None, "hvn", None, [], "osm", "Okhla Village locality"),
    ("TELCO Gazipur", "NH-24 / Ghazipur crossing", 28.6303, 77.3203, 3, 4, 7, None, "pd", None, [], "osm", "Ghazipur locality node"),
    ("Khajoori Khas Pusta Road", "Pushta Road", 28.7053, 77.2545, 2, 4, 6, None, "n", None, [], "osm", "Khajuri Khas node"),
    ("Near HaldiRam, Wazirpur", "Wazirpur Industrial Area", 28.6929, 77.1528, 2, 4, 6, None, "hd", None, [], "osm", "Haldiram's Wazirpur node"),
    ("C-1 Janakpuri", "Outer Ring Road", 28.6174, 77.0785, 2, 4, 6, None, "n", None, [], "osm", "C-1 Janakpuri block node"),
    ("Rajdhani Park", "Rohtak Road, Nangloi", 28.6823, 77.0439, 1, 4, 5, None, "h", None, [], "osm", "Rajdhani Park node"),
    ("Round About Seemapuri", "Seemapuri / Dilshad Garden side", 28.6811, 77.3278, 0, 4, 4, None, "ph", None, [], "osm", "Seemapuri (Old) node"),
    ("GTK Depot Jahangirpuri", "GT Karnal Road", 28.7307, 77.1570, 0, 4, 4, None, "hn", None, [], "osm", "GT Karnal Depot"),
    ("Gandhi Vihar Bus Stand", "Outer Ring Road / GT Road", 28.7209, 77.2140, 23, 3, 26, None, "whvdn", None, [2022, 2023], "osm", "Gandhi Vihar locality"),
    ("Moolchand Chowk", "Lala Lajpat Rai Marg / Ring Road", 28.5655, 77.2341, 14, 3, 17, None, "wd", None, [], "official", "TRiPC DMS 28°33'55.78\"N 77°14'2.89\"E"),
    ("Power House, Mahavir Enclave", "Palam–Dwarka side", 28.6000, 77.0790, 10, 3, 13, None, "", None, [], "curated", "Mahavir Enclave locality (powerhouse side)"),
    ("Under Pass Gajipur", "NH-24, Ghazipur", 28.6290, 77.3171, 10, 3, 13, None, "", None, [], "osm", "Ghazipur Underpass"),
    ("Peeragarhi Chowk", "Outer Ring Road / Rohtak Road", 28.6795, 77.0946, 10, 3, 13, None, "pd", None, [2022], "osm", "Peeragarhi Chowk node"),
    ("Akshardham Mandir", "NH-24 approach", 28.6178, 77.2795, 9, 3, 12, None, "w", None, [2024], "osm", "Akshardham complex node"),
    ("Dhaula Kuan", "Ring Road / Sardar Patel Marg", 28.5919, 77.1617, 8, 3, 11, None, "d", None, [2022], "osm", "Dhaula Kuan node"),
    ("Rajouri Garden", "Ring Road / Najafgarh Road", 28.6512, 77.1243, 8, 3, 11, None, "w", None, [], "osm", "Rajouri Garden metro junction"),
    ("Loni Road Crossing", "Loni Road, Shahdara", 28.7006, 77.2941, 8, 3, 11, None, "", None, [], "osm", "Delhi Loni Road Flyover"),
    ("Railway Under Pulprahladpur", "Mathura Road", 28.5019, 77.2907, 7, 3, 10, None, "n", None, [], "osm", "Pul Prahladpur area node"),
    ("Vijay Ghat", "Ring Road / Yamuna bank", 28.6576, 77.2448, 7, 3, 10, None, "", None, [], "osm", "Vijay Ghat node"),
    ("Toll Plaza Badarpur", "Mathura Road, Delhi–Faridabad border", 28.4933, 77.3034, 7, 3, 10, None, "h", None, [], "osm", "Badarpur Border bus stn (old toll site)"),
    ("Anand Vihar ISBT", "Vikas Marg / NH-24", 28.6490, 77.3183, 7, 3, 10, None, "", None, [2024], "osm", "Anand Vihar ISBT node"),
    ("Naraina", "Ring Road, Naraina Vihar", 28.6244, 77.1364, 7, 3, 10, None, "", None, [], "osm", "Naraina Vihar locality"),
    ("VIP College, Pitampura", "Outer Ring Road, Madhuban Chowk", 28.7033, 77.1323, 6, 3, 9, None, "", None, [], "osm", "Madhuban Chowk node (VIP college junction)"),
    ("Raja Harishchander Hospital", "Narela", 28.8406, 77.1033, 6, 3, 9, None, "", None, [], "osm", "RHC Hospital Narela"),
    ("Mundka Metro Station", "Rohtak Road, Mundka", 28.6824, 77.0306, 6, 3, 9, None, "p", None, [], "osm", "Mundka station area"),
    ("Nigam Bodh Ghat", "Ring Road, Yamuna bank", 28.6648, 77.2366, 5, 3, 8, None, "", None, [], "osm", "Nigambodh Ghat"),
    ("Flyover Raja Ram Marg", "Raja Ram Marg, Geeta Colony side", 28.6512, 77.2483, 5, 3, 8, None, "", None, [], "osm", "Geeta Colony Road Flyover"),
    ("Subhash Nagar Metro Station", "Najafgarh Road", 28.6404, 77.1190, 4, 3, 7, None, "", None, [], "curated", "Blue-line station corridor, Subhash Nagar"),
    ("Lajpat Rai Market (Lal Qila)", "Netaji Subhash Marg", 28.6574, 77.2360, 4, 3, 7, None, "", None, [], "osm", "Lajpat Rai Market node"),
    ("Shahdara Flyover", "GT Road, Shahdara", 28.6760, 77.2960, 4, 3, 7, None, "", None, [], "osm", "Shahdara Flyover"),
    ("Modi Mill Flyover", "Mathura Road", 28.5553, 77.2660, 4, 3, 7, None, "", None, [], "osm", "Modi Mill Flyover"),
    ("Prem Bari Pull", "Outer Ring Road, Azadpur side", 28.7000, 77.1585, 4, 3, 7, None, "h", None, [], "osm", "Prem Bari Pul node"),
    ("Jahangirpuri Bus Stand", "GT Karnal Road", 28.7260, 77.1627, 4, 3, 7, None, "n", None, [], "osm", "Jahangirpuri station node"),
    ("Chirag Delhi Flyover", "Outer Ring Road", 28.5416, 77.2317, 4, 3, 7, None, "", None, [], "osm", "Chirag Delhi Flyover"),
    ("Shastri Park Metro Station", "GT Road", 28.6684, 77.2503, 4, 3, 7, None, "", None, [], "osm", "Shastri Park metro"),
    ("Khampur Village", "GT Karnal Road north", 28.8233, 77.1279, 3, 3, 6, None, "n", None, [2022], "osm", "Khampur village node"),
    ("Azadpur Sabzi Mandi", "GT Karnal Road / Azadpur", 28.7219, 77.1649, 3, 3, 6, None, "", None, [2024], "osm", "Azadpur Mandi office node"),
    ("Keshopur T Point", "Outer Ring Road, Vikaspuri side", 28.6459, 77.0822, 3, 3, 6, None, "h", None, [], "osm", "Keshopur locality"),
    ("Tughlakabad Metro Station", "Mehrauli–Badarpur Road", 28.5033, 77.2989, 3, 3, 6, None, "", None, [], "osm", "Tughlakabad metro"),
    ("Near Manish Furniture Mkt, Nangloi Rd", "Rohtak Road, Nangloi", 28.6824, 77.0647, 3, 3, 6, None, "d", None, [], "curated", "Nangloi node — market strip on Rohtak Rd"),
    ("Jasola Vihar", "Mathura Road", 28.5427, 77.2913, 3, 3, 6, None, "", None, [], "osm", "Jasola Vihar locality"),
    ("ESI Hospital, Ring Road", "Ring Road, Basaidarapur", 28.6591, 77.1288, 2, 3, 5, None, "hd", None, [], "osm", "ESI Hospital node"),
    ("Khichripur", "Khichripur / NH-24 side", 28.6240, 77.3096, 2, 3, 5, None, "", None, [], "osm", "Khichripur Road"),
    ("Metro Station Sadar Bazar", "Sadarbazar Cantonment", 28.5769, 77.1116, 2, 3, 5, None, "n", None, [], "osm", "Sadar Bazar Cantt metro"),
    ("Santom Hospital, Outer Ring Rd", "Rohini–Pitampura side", 28.7140, 77.1383, 2, 3, 5, None, "", None, [], "osm", "Santom Hospital node"),
    ("Power House, Pitampura", "Outer Ring Road, Pitampura", 28.7033, 77.1393, 1, 3, 4, None, "", None, [], "curated", "Pitampura power-house side (AP Block)"),
    ("Panchsheel Flyover", "Outer Ring Road south", 28.5435, 77.2092, 1, 3, 4, None, "", None, [], "curated", "Panchsheel/Khelgaon flyover corridor"),
    ("Nizamuddin Yamuna Bridge", "Ring Road / Nizamuddin Road", 28.6034, 77.2543, 0, 3, 3, None, "", None, [], "osm", "Nizamuddin Road Bridge"),
    ("Dilshad Garden", "GT Road, Dilshad Garden", 28.6759, 77.3214, 0, 3, 3, None, "n", None, [], "osm", "Dilshad Garden node"),
    ("Gokalpuri", "Gokalpuri / Bhagirathi Vihar", 28.6954, 77.2913, 12, 2, 14, None, "d", None, [], "osm", "Gokalpuri locality"),
    ("Hyatt Hotel", "Ring Road, Bhikaji Cama Place", 28.5702, 77.1857, 9, 2, 11, None, "", None, [], "osm", "Hyatt Regency Delhi node"),
    ("Hanuman Mandir, Yamuna Bazar", "Ring Road, Yamuna bank", 28.6620, 77.2394, 8, 2, 10, None, "", None, [], "osm", "Yamuna Bazar node"),
    ("Tees Hazari Red Light", "Tis Hazari / Mori Gate side", 28.6671, 77.2166, 8, 2, 10, None, "", None, [], "osm", "Tis Hazari metro node"),
    ("Murga Mandi Flyover", "NH-24, Ghazipur murga mandi", 28.6234, 77.3240, 8, 2, 10, None, "", 10, [2020], "curated", "Ghazipur murga-mandi crossing on NH-24"),
    ("Sarita Vihar Flyover", "Mathura Road", 28.5365, 77.2846, 8, 2, 10, None, "", None, [], "osm", "Sarita Vihar node"),
    ("Durgapuri Chowk", "GT Road, Durgapuri (Shahdara)", 28.6799, 77.2820, 8, 2, 10, None, "", 4, [], "curated", "Durgapuri GT-Rd junction; TRiPC Shahdara list"),
    ("Mahipalpur Flyover", "NH-8, Mahipalpur", 28.5509, 77.1295, 8, 2, 10, None, "", None, [], "osm", "Mahipalpur Flyover"),
    ("DTC Bus Depot Nand Nagri", "Nand Nagri", 28.6978, 77.3057, 15, 1, 16, None, "", None, [], "osm", "Nand Nagri depot"),
    ("Harnam Palace, Ashok Nagar", "Ashok Nagar / Najafgarh Rd side", 28.6389, 77.1642, 12, 1, 13, None, "p", None, [], "curated", "Ashok Nagar chowk area (venue approximate)"),
    ("Sec-1,2 Red Light, Dwarka", "Road 221 × Mall Road, Dwarka", 28.5914, 77.0578, 11, 1, 12, None, "", 27, [], "official", "TRiPC DMS 28°35'29.16\"N 77°3'27.90\"E (Sector 7-9 Crossing)"),
    ("Nirankari Colony", "Burari Road", 28.7166, 77.2064, 9, 1, 10, None, "", 12, [], "osm", "Nirankari Colony"),
    ("Khajoori Chowk", "Main Wazirabad Road", 28.7098, 77.2735, 12, 0, 12, None, "", 15, [], "curated", "Khajoori Khas chowk; TRiPC NE list"),
    # ---- additions beyond the 2021 87-zone list ----
    ("ISBT Kashmere Gate", "Ring Road / ISBT", 28.6687, 77.2304, None, None, None, None, "", None, [2023, 2024], "osm", "Kashmere Gate ISBT node"),
    ("Kashmere Gate Chowk", "Kashmere Gate", 28.6674, 77.2282, None, None, None, None, "", None, [2023], "osm", "Kashmere Gate junction"),
    ("Mori Gate Roundabout", "Mori Gate", 28.6642, 77.2237, None, None, None, None, "", None, [2023], "osm", "Mori Gate node"),
    ("Britannia Chowk", "Ring Road, Punjabi Bagh north", 28.6835, 77.1329, None, None, None, None, "", None, [2022, 2023], "osm", "Britannia Chowk node"),
    ("Ashram Chowk", "Ring Road / Mathura Road", 28.5855, 77.2597, None, None, None, None, "", None, [2022], "curated", "Ashram Chowk junction"),
    ("Azadpur Chowk", "Ring Road / GT Karnal Road", 28.7058, 77.1819, 4, 2, 6, None, "", 15, [2020], "osm", "Azadpur metro junction"),
    ("Signature Bridge approach", "Wazirabad Road", 28.7055, 77.2332, None, None, None, None, "", 16, [], "osm", "Signature Bridge north node"),
    ("Rajokri Flyover", "NH-8", 28.5969, 77.1148, 6, 2, 8, None, "", None, [2020, 2024], "curated", "Rajokri flyover, NH-8"),
    ("Yashobhoomi Convention Centre", "Dwarka Sector 25", 28.5508, 77.0453, None, None, None, None, "", None, [2024], "osm", "Yashobhoomi (IICC) node"),
    ("Shivaji Park Metro Station", "Rohtak Road, Punjabi Bagh west", 28.6746, 77.1149, None, None, None, None, "", 10, [], "curated", "Green-line station junction"),
    ("SKV Ghitorni", "MG Road, Ghitorni", 28.4931, 77.1425, None, None, None, None, "", 1, [], "osm", "Ghitorni locality (TRiPC New Delhi list)"),
    ("GBSSS Gokulpuri", "Gokulpuri", 28.7025, 77.2861, None, None, None, None, "", 1, [], "osm", "Gokulpuri node (TRiPC NE list)"),
    ("Ali Village", "Ali village, Jaitpur side", 28.5161, 77.2966, None, None, None, None, "", 6, [], "osm", "Ali Village node (TRiPC SE list)"),
    ("Sarvodaya School, Hari Nagar Ashram", "Hari Nagar, Ashram side", 28.5827, 77.2685, None, None, None, None, "", 16, [], "curated", "Hari Nagar locality near Ashram (TRiPC SE list)"),
    ("Khera More", "Najafgarh side", 28.6105, 77.0330, None, None, None, None, "", 6, [], "curated", "Khera More junction (TRiPC SW list)"),
    ("GBSSS-2 Najafgarh", "Najafgarh town", 28.6092, 77.0674, None, None, None, None, "", 16, [], "curated", "Najafgarh town centre (TRiPC SW list)"),
    ("Wazirpur Depot", "Wazirpur DTC depot side", 28.6936, 77.1554, None, None, None, None, "", None, [2023], "osm", "Wazirpur Depot node"),
]

FLAG_LABEL = {"n": "night", "p": "pedestrian", "w": "two-wheeler",
              "h": "hit-and-run", "d": "day", "v": "heavy-vehicle"}


def _severity(fatal, killed, deaths_3y, top10):
    """Coarse tier straight off the published counts: 'high' for the deadliest
    zones (>=5 fatal in 2021, or a published multi-year top-10 entry / heavy
    3-year death toll), 'watch' for the rest — every entry is an official
    crash-prone zone regardless."""
    if (fatal or 0) >= 5 or (killed or 0) >= 6 or (deaths_3y or 0) >= 12 \
            or len(top10) >= 2:
        return "high"
    if (fatal or 0) >= 3 or top10 or (deaths_3y or 0) >= 6:
        return "medium"
    return "watch"


SPOTS = [
    {
        "name": name, "road": road, "lat": lat, "lon": lon,
        "crashes_2021": {"simple": simple, "fatal": fatal, "total": total},
        "killed_2021": killed,
        "subtypes": [FLAG_LABEL[c] for c in dict.fromkeys(flags)],
        "deaths_2019_21": deaths_3y,
        "top10_years": top10,
        "severity": _severity(fatal, killed, deaths_3y, top10),
        "coord_source": coord, "coord_note": note,
    }
    for (name, road, lat, lon, simple, fatal, total, killed, flags,
         deaths_3y, top10, coord, note) in S
]

# exposure radius for a spot — DTP defines a zone as a 500m-diameter
# circle, so a point within ~250m of centre is inside the zone.
ZONE_RADIUS_M = 250.0


def _hav_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _point_seg_m(lat, lon, a, b):
    """Metres from point to segment a->b, planar approx fine at <1km scale."""
    lat_r = math.radians(lat)
    kx = 111320.0 * math.cos(lat_r)
    ky = 110540.0
    ax, ay = a[0] * kx, a[1] * ky
    bx, by = b[0] * kx, b[1] * ky
    px, py = lon * kx, lat * ky
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    t = 0.0 if seg2 < 1e-6 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def spots_near(coords, radius_m=ZONE_RADIUS_M):
    """Black spots whose zone circle a lon/lat path touches; returns
    [(spot, min_dist_m)] sorted by distance. coords = [[lon, lat], ...]."""
    if not coords or len(coords) < 2:
        return []
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    out = []
    pad = radius_m / 90000.0  # generous deg pad
    for s in SPOTS:
        if s["lon"] < min(xs) - pad or s["lon"] > max(xs) + pad \
                or s["lat"] < min(ys) - pad or s["lat"] > max(ys) + pad:
            continue
        d = min(_point_seg_m(s["lat"], s["lon"], coords[i], coords[i + 1])
                for i in range(len(coords) - 1))
        if d <= radius_m:
            out.append((s, round(d)))
    out.sort(key=lambda t: t[1])
    return out


def spots_near_geometry(geometry, radius_m=ZONE_RADIUS_M):
    return spots_near((geometry or {}).get("coordinates") or [], radius_m)


def geojson():
    feats = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
        "properties": {k: s[k] for k in
                       ("name", "road", "severity", "crashes_2021",
                        "killed_2021", "deaths_2019_21", "subtypes",
                        "top10_years", "coord_source", "coord_note")},
    } for s in SPOTS]
    return {
        "type": "FeatureCollection",
        "features": feats,
        "metadata": {
            "count": len(feats),
            "zone_radius_m": ZONE_RADIUS_M,
            "sources": [
                "Delhi Traffic Police, Delhi Crash Report 2021 — Tables 6.25-6.28, 6.33-6.38 (87 crash-prone zones)",
                "IIT-Delhi TRiPC / Delhi Transport Dept / Vital Strategies, Delhi Road Safety Report 'Data to Action' (2019-21) district reports",
                "Delhi Traffic Police annual top-10 lists 2022-2024 as published in Indian Express / TOI / NDTV",
            ],
        },
    }
