import json
from io import BytesIO
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st
import numpy as np
import altair as alt

DATA_DIR = Path(__file__).resolve().parent
SCHOOL_GEOJSON_PATH = DATA_DIR / "penelitian2.geojson"
UNI_GEOJSON_PATH = DATA_DIR / "universitas.geojson"
ALUMNI_EXCEL_PATH = DATA_DIR / "Mapping_Sekolah_Dummy_Berdasarkan_Wilayah.xlsx"


@st.cache_data
def load_university_points():
    if not UNI_GEOJSON_PATH.exists():
        return pd.DataFrame(
            [
                {
                    "nama": "Universitas Esa Unggul Kebon Jeruk",
                    "Longitude": 106.7836,
                    "Latitude": -6.2019,
                },
                {
                    "nama": "Universitas Esa Unggul Citra Raya",
                    "Longitude": 106.5339,
                    "Latitude": -6.22683,
                },
                {
                    "nama": "Universitas Esa Unggul Bekasi",
                    "Longitude": 106.98433,
                    "Latitude": -6.17366,
                },
            ]
        )

    with open(UNI_GEOJSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    rows = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [None, None])
        rows.append(
            {
                "nama": props.get("nama", ""),
                "Longitude": coords[0],
                "Latitude": coords[1],
            }
        )
    return pd.DataFrame(rows)


@st.cache_data
def load_school_data():
    if not SCHOOL_GEOJSON_PATH.exists():
        return pd.DataFrame(
            [
                {
                    "NAME": "SMP Sample Jakarta",
                    "LEVEL": "Junior High School (SMP)",
                    "ADDRESS": "Jl. Sample No. 1",
                    "DISTRICT": "Kota Jakarta Selatan",
                    "PROVINCE": "Prov. D.K.I. Jakarta",
                    "Longitude": 106.771,
                    "Latitude": -6.2828,
                    "STATUS": "Negeri",
                    "POTENSI_SKOR": 78,
                }
            ]
        )

    with open(SCHOOL_GEOJSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [None, None])
        rows.append(
            {
                "NAME": props.get("NAME", props.get("name", "")),
                "LEVEL": props.get("LEVEL", "-"),
                "ADDRESS": props.get("ADDRESS", ""),
                "DISTRICT": props.get("DISTRICT", ""),
                "PROVINCE": props.get("PROVINCE", ""),
                "Longitude": coords[0],
                "Latitude": coords[1],
                "STATUS": props.get("STATUS", "Sekolah"),
                "POTENSI_SKOR": 60 + hash(props.get("NAME", "")) % 40,
            }
        )

    df = pd.DataFrame(rows)
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df = df.dropna(subset=["Longitude", "Latitude"]).reset_index(drop=True)

    # Hanya tampilkan SMA & SMK (setara/sederajat) — SD & SMP tidak relevan untuk rekrutmen mahasiswa
    sma_smk_mask = df["LEVEL"].str.contains(
        "Senior High School|Vocational School|SMA|SMK|MA|MAK", na=False, case=False
    )
    if sma_smk_mask.any():
        df = df.loc[sma_smk_mask].copy()

    jakarta_mask = df["PROVINCE"].str.contains(
        "Jakarta|Banten|Bekasi|Tangerang|Depok|Bogor", na=False, case=False
    )
    if jakarta_mask.any():
        df = df.loc[jakarta_mask].copy()

    return df.reset_index(drop=True)


@st.cache_data
def load_alumni_data() -> pd.DataFrame:
    """Load dummy alumni data dari file Excel."""
    if not ALUMNI_EXCEL_PATH.exists():
        return pd.DataFrame(columns=["ALUMNI_NAME", "SCHOOL_NAME", "GRAD_YEAR", "PROGRAM_INTEREST", "NOTE"])

    try:
        # Baca Excel — baris 0 adalah header ganda (NO/NAMA/kolom sekolah), baris 1+ adalah data
        raw = pd.read_excel(ALUMNI_EXCEL_PATH, skiprows=1, header=0)
        raw.columns = ["NO", "ALUMNI_NAME", "SCHOOL_NAME"]
        raw = raw.dropna(subset=["ALUMNI_NAME", "SCHOOL_NAME"]).copy()
        raw = raw[raw["ALUMNI_NAME"].astype(str).str.strip() != ""].copy()

        # Enrichment: buat kolom tambahan yang dibutuhkan aplikasi
        rng = np.random.default_rng(seed=42)
        n = len(raw)

        program_pool = [
            "Teknik Informatika", "Sistem Informasi", "Manajemen Bisnis",
            "Ilmu Komunikasi", "Desain Komunikasi Visual", "Teknik Industri",
            "Psikologi", "Hukum", "Kedokteran", "Arsitektur",
        ]
        raw["GRAD_YEAR"] = rng.integers(2020, 2025, size=n)
        raw["PROGRAM_INTEREST"] = [program_pool[i % len(program_pool)] for i in range(n)]
        raw["NOTE"] = "Data alumni dari mapping sekolah."

        return raw[["ALUMNI_NAME", "SCHOOL_NAME", "GRAD_YEAR", "PROGRAM_INTEREST", "NOTE"]].reset_index(drop=True)

    except Exception as e:
        st.warning(f"Gagal memuat data alumni: {e}")
        return pd.DataFrame(columns=["ALUMNI_NAME", "SCHOOL_NAME", "GRAD_YEAR", "PROGRAM_INTEREST", "NOTE"])


def init_session_state():
    if "schools" not in st.session_state:
        school_df = load_school_data()
        if school_df.empty:
            school_df = pd.DataFrame(
                [
                    {
                        "NAME": "Sekolah Mitra Sample",
                        "LEVEL": "Senior High School (SMA)",
                        "ADDRESS": "Jl. Contoh No. 123",
                        "DISTRICT": "Kota Tangerang",
                        "PROVINCE": "Prov. Banten",
                        "Longitude": 106.6018,
                        "Latitude": -6.1250,
                        "STATUS": "Negeri",
                        "POTENSI_SKOR": 82,
                    }
                ]
            )
        st.session_state.schools = school_df

    if "universities" not in st.session_state:
        uni_df = load_university_points()
        uni_df["Longitude"] = pd.to_numeric(uni_df["Longitude"], errors="coerce")
        uni_df["Latitude"] = pd.to_numeric(uni_df["Latitude"], errors="coerce")
        st.session_state.universities = uni_df.dropna(subset=["Longitude", "Latitude"]).reset_index(drop=True)

    if "alumni" not in st.session_state:
        alumni_df = load_alumni_data()
        if alumni_df.empty:
            alumni_df = pd.DataFrame(
                [
                    {
                        "ALUMNI_NAME": "Rina Wijaya",
                        "SCHOOL_NAME": "SMA Negeri 8 Jakarta",
                        "GRAD_YEAR": 2023,
                        "PROGRAM_INTEREST": "Teknik Informatika",
                        "NOTE": "Alumni terdaftar di UEU, alumni kelas unggulan.",
                    },
                    {
                        "ALUMNI_NAME": "Budi Santoso",
                        "SCHOOL_NAME": "SMKN 26 Jakarta",
                        "GRAD_YEAR": 2022,
                        "PROGRAM_INTEREST": "Manajemen Bisnis",
                        "NOTE": "Prospek marketing kuat dari jurusan vokasi.",
                    },
                ]
            )
        st.session_state.alumni = alumni_df

    if "visits" not in st.session_state:
        st.session_state.visits = pd.DataFrame(
            [
                {
                    "VISIT_TITLE": "SMA Negeri 8 Jakarta",
                    "REGION": "Jakarta Barat",
                    "DATE": "2024-10-01",
                    "STATUS": "Done",
                    "PRIORITY": "High",
                    "NOTE": "Follow-up alumni club event.",
                },
                {
                    "VISIT_TITLE": "SMA Labschool Jakarta",
                    "REGION": "Jakarta Selatan",
                    "DATE": "2024-10-06",
                    "STATUS": "Pending",
                    "PRIORITY": "Medium",
                    "NOTE": "Persiapan presentasi program digital.",
                },
                {
                    "VISIT_TITLE": "MAN 2 Jakarta",
                    "REGION": "Jakarta Pusat",
                    "DATE": "2024-10-12",
                    "STATUS": "Scheduled",
                    "PRIORITY": "High",
                    "NOTE": "Agenda persiapan pameran kampus.",
                },
                {
                    "VISIT_TITLE": "SMAN 1 Tangerang",
                    "REGION": "Tangerang",
                    "DATE": "2024-10-16",
                    "STATUS": "Follow-up Required",
                    "PRIORITY": "Urgent",
                    "NOTE": "Permintaan proposal detail.",
                },
            ]
        )


def apply_custom_styles():
    st.markdown(
        """
        <style>
        :root {
            --ueu-navy: #3b82f6;      /* Bright blue untuk dark mode */
            --ueu-navy-dark: #f8fafc; /* Off-white untuk judul utama */
            --ueu-bg: #0b0f19;        /* Deep dark blue-black */
            --ueu-border: #1e293b;    /* Dark slate border */
            --ueu-text: #e2e8f0;      /* Slate-200 */
            --ueu-muted: #94a3b8;     /* Slate-400 */
            --ueu-soft-blue: #1e293b; /* Slate-800 */
            --ueu-green: #2ecc71;
            --ueu-yellow: #f1c40f;
            --ueu-red: #e74c3c;
        }
        .stApp {
            background: var(--ueu-bg);
            color: var(--ueu-text);
        }
        [data-testid="stHeader"] {
            background: rgba(11, 15, 25, 0.9);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--ueu-border);
        }
        [data-testid="stSidebar"] {
            background: #0b0f19;
            border-right: 1px solid var(--ueu-border);
        }
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 28px;
        }
        [data-testid="stSidebar"] h1 {
            font-size: 22px;
            color: #ffffff;
            letter-spacing: 0;
            margin-bottom: 0;
        }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            color: var(--ueu-muted);
        }
        [data-testid="stSidebar"] [role="radiogroup"] label {
            border-radius: 7px;
            padding: 8px 10px;
            margin: 2px 0;
            min-height: 42px;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
            background: #1e293b;
            color: #ffffff;
            border-left: 4px solid var(--ueu-navy);
            box-shadow: none;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {
            color: #ffffff;
            font-weight: 700;
        }
        [data-testid="stSidebar"] hr {
            border-color: var(--ueu-border);
            margin: 22px 0;
        }
        .block-container {
            padding-top: 2.1rem;
            padding-bottom: 3rem;
            max-width: 1320px;
        }
        div[data-testid="stToolbar"] {
            display: none;
        }
        h1, h2, h3 {
            color: var(--ueu-navy-dark);
            letter-spacing: 0;
        }
        .stButton>button {
            border-radius: 7px;
            border: 1px solid var(--ueu-border);
            background: #1e293b;
            color: #ffffff;
            font-weight: 700;
            min-height: 42px;
        }
        .stButton>button[kind="primary"],
        .stDownloadButton>button[kind="primary"] {
            background: var(--ueu-navy);
            border-color: var(--ueu-navy);
            color: #ffffff;
        }
        .stDownloadButton>button {
            border-radius: 7px;
            background: #1e293b;
            color: #ffffff;
            font-weight: 700;
            min-height: 42px;
        }
        .page-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 18px;
            margin-bottom: 22px;
        }
        .page-kicker {
            color: var(--ueu-muted);
            font-size: 13px;
            margin-bottom: 6px;
        }
        .page-title {
            color: var(--ueu-navy-dark);
            font-size: 32px;
            line-height: 1.1;
            font-weight: 800;
            margin-bottom: 8px;
        }
        .section-subtitle {
            color: var(--ueu-muted);
            margin-top: 0;
            max-width: 650px;
            font-size: 16px;
        }
        .admin-pill {
            border: 1px solid var(--ueu-border);
            border-radius: 8px;
            background: #131b2e;
            padding: 10px 14px;
            color: var(--ueu-navy-dark);
            min-width: 178px;
            text-align: right;
            box-shadow: 0 3px 12px rgba(0, 0, 0, 0.2);
        }
        .admin-pill strong {
            display: block;
            font-size: 14px;
        }
        .admin-pill span {
            color: var(--ueu-muted);
            font-size: 12px;
        }
        .metric-card, .content-card, .filter-card, .table-card {
            border: 1px solid var(--ueu-border);
            border-radius: 8px;
            background: #131b2e;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
        }
        .metric-card {
            min-height: 116px;
            padding: 18px 20px;
            margin-bottom: 16px;
            position: relative;
            overflow: hidden;
        }
        .metric-icon {
            width: 38px;
            height: 38px;
            border-radius: 8px;
            display: grid;
            place-items: center;
            background: #1e293b;
            color: #60a5fa;
            font-weight: 800;
            margin-bottom: 13px;
        }
        .metric-card h3 {
            color: var(--ueu-muted);
            font-size: 13px;
            margin: 0 0 6px 0;
            font-weight: 700;
        }
        .metric-card h2 {
            color: var(--ueu-navy-dark);
            font-size: 28px;
            margin: 0;
            line-height: 1;
            font-weight: 800;
        }
        .metric-change {
            color: #2ecc71;
            font-size: 12px;
            font-weight: 700;
            margin-top: 9px;
        }
        .content-card {
            padding: 18px;
            margin-bottom: 18px;
        }
        .filter-card {
            padding: 16px 18px 4px;
            margin-bottom: 18px;
        }
        .soft-label {
            color: var(--ueu-muted);
            font-size: 12px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 4px;
        }
        .card-box {
            border-radius: 8px;
            background: #131b2e;
            padding: 16px;
            border: 1px solid var(--ueu-border);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
        }
        .kanban-card {
            background: #131b2e;
            border-radius: 8px;
            border: 1px solid var(--ueu-border);
            padding: 16px;
            margin-bottom: 12px;
            min-height: 118px;
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.2);
        }
        .kanban-card strong {
            display: block;
            color: var(--ueu-text);
            margin-bottom: 8px;
        }
        .kanban-card small {
            color: var(--ueu-muted);
        }
        .badge {
            display: inline-flex;
            align-items: center;
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
            font-weight: 800;
            text-transform: uppercase;
            margin-bottom: 12px;
        }
        .badge-blue { background: #1e3a8a; color: #60a5fa; }
        .badge-green { background: #064e3b; color: #34d399; }
        .badge-yellow { background: #78350f; color: #fbbf24; }
        .badge-red { background: #7f1d1d; color: #f87171; }
        .status-dot {
            display: inline-block;
            width: 8px;
            height: 24px;
            border-radius: 999px;
            margin-right: 8px;
            vertical-align: middle;
        }
        .calendar-shell {
            border: 1px solid var(--ueu-border);
            border-radius: 8px;
            overflow: hidden;
            background: #131b2e;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
        }
        .calendar-grid {
            display: grid;
            grid-template-columns: repeat(7, minmax(92px, 1fr));
        }
        .calendar-head {
            background: #1e293b;
            color: var(--ueu-muted);
            text-align: center;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0.06em;
            padding: 13px 6px;
            text-transform: uppercase;
            border-right: 1px solid var(--ueu-border);
        }
        .calendar-cell {
            min-height: 124px;
            padding: 10px;
            border-top: 1px solid var(--ueu-border);
            border-right: 1px solid var(--ueu-border);
            color: var(--ueu-text);
        }
        .calendar-date {
            font-weight: 800;
            margin-bottom: 8px;
            font-size: 14px;
        }
        .calendar-event {
            border-radius: 5px;
            padding: 8px 9px;
            font-size: 12px;
            font-weight: 700;
            border-left: 4px solid var(--ueu-navy);
            background: #1e293b;
            color: #ffffff;
        }
        .calendar-event.done {
            background: #064e3b;
            border-left-color: var(--ueu-green);
        }
        .calendar-event.pending {
            background: #78350f;
            border-left-color: var(--ueu-yellow);
        }
        .calendar-event.follow {
            background: #7f1d1d;
            border-left-color: var(--ueu-red);
        }
        [data-testid="stDataFrame"] {
            border: 1px solid var(--ueu-border);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
        }
        div[data-baseweb="select"] > div,
        .stTextInput input,
        .stNumberInput input,
        .stDateInput input,
        .stTextArea textarea {
            border-radius: 7px;
            border-color: var(--ueu-border) !important;
            background: #131b2e !important;
            color: #ffffff !important;
        }
        @media (max-width: 900px) {
            .page-header {
                display: block;
            }
            .admin-pill {
                text-align: left;
                margin-top: 12px;
            }
            .calendar-grid {
                grid-template-columns: repeat(2, minmax(130px, 1fr));
            }
            .calendar-head {
                display: none;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str, kicker: str = "UEU DSS"):
    st.markdown(
        f"""
        <div class="page-header">
            <div>
                <div class="page-kicker">{kicker}</div>
                <div class="page-title">{title}</div>
                <p class="section-subtitle">{subtitle}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, icon: str, note: str = "+ 0.0%", suffix: str = "dibanding periode lalu"):
    note_text = f"{note} {suffix}".strip()
    return f"""
    <div class="metric-card">
        <div class="metric-icon">{icon}</div>
        <h3>{label}</h3>
        <h2>{value}</h2>
        <div class="metric-change">{note_text}</div>
    </div>
    """


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Sheet1") -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


def save_universities_geojson(df: pd.DataFrame):
    features = []
    for _, row in df.dropna(subset=["Longitude", "Latitude"]).iterrows():
        features.append(
            {
                "type": "Feature",
                "properties": {"nama": str(row.get("nama", ""))},
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        float(row.get("Longitude")),
                        float(row.get("Latitude")),
                    ],
                },
            }
        )

    with open(UNI_GEOJSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False, indent=2)
    load_university_points.clear()


def get_selected_index(df: pd.DataFrame, label_col: str, selected_label: str):
    matches = df.index[df[label_col].astype(str) == selected_label].tolist()
    return matches[0] if matches else None


def get_template_school() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "NAME": "SMAN 8 Jakarta",
                "LEVEL": "Senior High School (SMA)",
                "ADDRESS": "Jl. Sultan Agung No. 1",
                "PROVINCE": "Prov. D.K.I. Jakarta",
                "DISTRICT": "Jakarta Barat",
                "Longitude": 106.780,
                "Latitude": -6.190,
                "STATUS": "Negeri",
                "POTENSI_SKOR": 92,
            }
        ]
    )


def get_template_alumni() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ALUMNI_NAME": "Nama Alumni",
                "SCHOOL_NAME": "SMAN 8 Jakarta",
                "GRAD_YEAR": 2024,
                "PROGRAM_INTEREST": "Teknik Informatika",
                "NOTE": "Contoh catatan alumni.",
            }
        ]
    )


def render_sidebar():
    st.sidebar.markdown("# Esa Unggul WebGIS")
    st.sidebar.caption("Recruitment System")
    st.sidebar.markdown("---")
    page = st.sidebar.radio(
        "Menu",
        [
            "Dashboard",
            "Peta Rekrutmen Interaktif",
            "Data Sekolah",
            "Marketing Visits",
            "Laporan",
        ],
        index=0,
        label_visibility="visible",
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div class="card-box" style="background:#1e293b; box-shadow:none; border:1px solid #334155;">
            <div class="soft-label" style="color:#94a3b8;">System Status</div>
            <strong style="color:#60a5fa;">GIS Engine Active</strong>
            <div style="color:#cbd5e1; font-size:12px; margin-top:6px;">Data sekolah dan kampus siap dianalisis.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return page


def add_zone_information(schools_df, campuses_df):
    if schools_df.empty or campuses_df.empty:
        schools_df = schools_df.copy()
        schools_df["ZONE"] = "Zona Perluasan"
        schools_df["ZONE_COLOR"] = [[189, 189, 189, 180]] * len(schools_df)
        schools_df["DISTANCE_TO_CAMPUS"] = 999.0
        return schools_df

    # Make sure coordinates are numeric
    schools_df = schools_df.copy()
    schools_df["Latitude"] = pd.to_numeric(schools_df["Latitude"], errors="coerce")
    schools_df["Longitude"] = pd.to_numeric(schools_df["Longitude"], errors="coerce")
    
    campuses_df = campuses_df.copy()
    campuses_df["Latitude"] = pd.to_numeric(campuses_df["Latitude"], errors="coerce")
    campuses_df["Longitude"] = pd.to_numeric(campuses_df["Longitude"], errors="coerce")

    schools_clean = schools_df.dropna(subset=["Latitude", "Longitude"])
    campuses_clean = campuses_df.dropna(subset=["Latitude", "Longitude"])

    # Initialize default columns aligned with original indices
    schools_df["ZONE"] = "Zona Perluasan"
    schools_df["ZONE_COLOR"] = pd.Series([[189, 189, 189, 180]] * len(schools_df), index=schools_df.index)
    schools_df["DISTANCE_TO_CAMPUS"] = 999.0

    if schools_clean.empty or campuses_clean.empty:
        return schools_df

    s_lats = schools_clean["Latitude"].to_numpy()
    s_lons = schools_clean["Longitude"].to_numpy()
    c_lats = campuses_clean["Latitude"].to_numpy()
    c_lons = campuses_clean["Longitude"].to_numpy()

    r = 6371.0  # Earth radius in km
    
    # Broadcast to (N, M)
    lat1 = np.radians(s_lats[:, np.newaxis])
    lon1 = np.radians(s_lons[:, np.newaxis])
    lat2 = np.radians(c_lats[np.newaxis, :])
    lon2 = np.radians(c_lons[np.newaxis, :])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    distances = r * c  # shape (N, M)
    
    min_distances = np.min(distances, axis=1)
    
    # Map to zones berdasarkan radius buffer baru
    zones = np.where(min_distances <= 5.0, "Zona Inti",
            np.where(min_distances <= 10.0, "Zona Potensial",
            np.where(min_distances <= 15.0, "Zona Ekspansi", "Zona Perluasan")))
    
    # Colors (R, G, B, Alpha) - Optimasi untuk peta gelap (glow effect)
    color_map = {
        "Zona Inti": [46, 213, 115, 200],       # Green (lebih terang)
        "Zona Potensial": [255, 211, 42, 200],   # Yellow (lebih terang)
        "Zona Ekspansi": [44, 130, 201, 200],    # Blue (lebih terang)
        "Zona Perluasan": [168, 180, 192, 150],  # Grey
    }

    schools_df.loc[schools_clean.index, "ZONE"] = zones
    schools_df.loc[schools_clean.index, "DISTANCE_TO_CAMPUS"] = min_distances
    schools_df.loc[schools_clean.index, "ZONE_COLOR"] = pd.Series([color_map[z] for z in zones], index=schools_clean.index)

    return schools_df


def zone_summary_cards(inti_cnt, inti_pct, pot_cnt, pot_pct, eks_cnt, eks_pct, per_cnt, per_pct):
    return f"""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 10px;">
        <div style="background:#062f1c; border:1px solid #14864b; border-radius:8px; padding:12px; text-align:center;">
            <div style="color:#2ecc71; font-size:11px; font-weight:800; text-transform:uppercase;">Zona Inti</div>
            <div style="color:#2ecc71; font-size:20px; font-weight:800; margin:4px 0;">{inti_cnt}</div>
            <div style="color:#2ecc71; font-size:11px; font-weight:700;">Sekolah ({inti_pct:.0f}%)</div>
        </div>
        <div style="background:#3c2b0d; border:1px solid #9a6b00; border-radius:8px; padding:12px; text-align:center;">
            <div style="color:#f1c40f; font-size:11px; font-weight:800; text-transform:uppercase;">Zona Potensial</div>
            <div style="color:#f1c40f; font-size:20px; font-weight:800; margin:4px 0;">{pot_cnt}</div>
            <div style="color:#f1c40f; font-size:11px; font-weight:700;">Sekolah ({pot_pct:.0f}%)</div>
        </div>
        <div style="background:#0b2545; border:1px solid #005da4; border-radius:8px; padding:12px; text-align:center;">
            <div style="color:#3498db; font-size:11px; font-weight:800; text-transform:uppercase;">Zona Ekspansi</div>
            <div style="color:#3498db; font-size:20px; font-weight:800; margin:4px 0;">{eks_cnt}</div>
            <div style="color:#3498db; font-size:11px; font-weight:700;">Sekolah ({eks_pct:.0f}%)</div>
        </div>
        <div style="background:#1e293b; border:1px solid #475569; border-radius:8px; padding:12px; text-align:center;">
            <div style="color:#94a3b8; font-size:11px; font-weight:800; text-transform:uppercase;">Zona Perluasan</div>
            <div style="color:#cbd5e1; font-size:20px; font-weight:800; margin:4px 0;">{per_cnt}</div>
            <div style="color:#94a3b8; font-size:11px; font-weight:700;">Sekolah ({per_pct:.0f}%)</div>
        </div>
    </div>
    """


def render_dashboard_bottom_row(schools_with_zones):
    total_schools = len(schools_with_zones)
    if total_schools > 0:
        inti_cnt = len(schools_with_zones[schools_with_zones["ZONE"] == "Zona Inti"])
        pot_cnt = len(schools_with_zones[schools_with_zones["ZONE"] == "Zona Potensial"])
        eks_cnt = len(schools_with_zones[schools_with_zones["ZONE"] == "Zona Ekspansi"])
        per_cnt = len(schools_with_zones[schools_with_zones["ZONE"] == "Zona Perluasan"])

        inti_pct = (inti_cnt / total_schools) * 100
        pot_pct = (pot_cnt / total_schools) * 100
        eks_pct = (eks_cnt / total_schools) * 100
        per_pct = (per_cnt / total_schools) * 100
    else:
        inti_cnt, pot_cnt, eks_cnt, per_cnt = 48, 62, 89, 34
        inti_pct, pot_pct, eks_pct, per_pct = 38, 32, 20, 10

    st.markdown("### Ringkasan Wilayah & Strategi Rekrutmen")
    
    col_left, col_right = st.columns([2.3, 1])
    
    with col_left:
        st.markdown('<div class="content-card" style="padding: 16px;">', unsafe_allow_html=True)
        st.markdown("<strong style='font-size:15px; color:var(--ueu-navy-dark);'>Ringkasan Wilayah per Zona (Semua Kampus)</strong>", unsafe_allow_html=True)
        st.markdown(zone_summary_cards(inti_cnt, inti_pct, pot_cnt, pot_pct, eks_cnt, eks_pct, per_cnt, per_pct), unsafe_allow_html=True)
        
        # Sub-row for Charts
        st.markdown("<br>", unsafe_allow_html=True)
        c_trend, c_top, c_pie = st.columns([1.2, 1.2, 1])
        
        with c_trend:
            st.markdown("<strong style='font-size:13px; color:var(--ueu-navy-dark);'>Tren Penerimaan Mahasiswa Baru</strong>", unsafe_allow_html=True)
            trend_data = pd.DataFrame({
                "Tahun": [2020, 2021, 2022, 2023, 2024] * 3,
                "Kampus": ["Kampus Jakarta"] * 5 + ["Kampus Tangerang"] * 5 + ["Kampus Bekasi"] * 5,
                "Penerimaan": [1500, 1800, 2200, 2600, 3100,
                               800, 1100, 1400, 1900, 2400,
                               400, 550, 700, 950, 1200]
            })
            st.line_chart(trend_data, x="Tahun", y="Penerimaan", color="Kampus", height=200)
            
        with c_top:
            st.markdown("<strong style='font-size:13px; color:var(--ueu-navy-dark);'>Top 5 Wilayah Potensial</strong>", unsafe_allow_html=True)
            top5 = schools_with_zones.sort_values(by="POTENSI_SKOR", ascending=False).head(5)
            if not top5.empty:
                st.dataframe(top5[["NAME", "DISTRICT", "POTENSI_SKOR"]], hide_index=True, height=200)
            else:
                st.info("Tidak ada data sekolah.")
                 
        with c_pie:
            st.markdown("<strong style='font-size:13px; color:var(--ueu-navy-dark);'>Distribusi Sekolah per Zona</strong>", unsafe_allow_html=True)
            source = pd.DataFrame({
                "Zona": ["Zona Inti", "Zona Potensial", "Zona Ekspansi", "Zona Perluasan"],
                "Value": [inti_cnt, pot_cnt, eks_cnt, per_cnt]
            })
            chart = alt.Chart(source).mark_arc(innerRadius=40).encode(
                theta=alt.Theta(field="Value", type="quantitative"),
                color=alt.Color(field="Zona", type="nominal", scale=alt.Scale(
                    domain=["Zona Inti", "Zona Potensial", "Zona Ekspansi", "Zona Perluasan"],
                    range=["#20c66b", "#f7c514", "#005da4", "#bdbebe"]
                )),
                tooltip=["Zona", "Value"]
            ).properties(height=180)
            st.altair_chart(chart, use_container_width=True)
            
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_right:
        st.markdown('<div class="content-card" style="padding: 16px; height: 100%;">', unsafe_allow_html=True)
        st.markdown("<strong style='font-size:15px; color:var(--ueu-navy-dark);'>Rekomendasi Strategi per Kampus</strong>", unsafe_allow_html=True)
        
        st.markdown("""
        <div style="font-size:12px; margin-top: 10px;">
            <table style="width:100%; border-collapse: collapse;">
                <thead>
                    <tr style="border-bottom: 2px solid var(--ueu-border); text-align: left;">
                        <th style="padding: 6px 0; font-weight: bold; color: var(--ueu-navy-dark);">Kampus</th>
                        <th style="padding: 6px 0; font-weight: bold; color: var(--ueu-navy-dark);">Strategi Utama</th>
                        <th style="padding: 6px 0; font-weight: bold; color: var(--ueu-navy-dark); text-align: right;">Prioritas</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom: 1px solid var(--ueu-border);">
                        <td style="padding: 8px 0; font-weight: 700; color: #60a5fa;">🏛️ Jakarta</td>
                        <td style="padding: 8px 0; color: var(--ueu-muted);">Promosi Digital, Kerja sama SMA, Open House</td>
                        <td style="padding: 8px 0; text-align: right;"><span class="badge badge-red">Tinggi</span></td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--ueu-border);">
                        <td style="padding: 8px 0; font-weight: 700; color: #2ecc71;">🏛️ Tangerang</td>
                        <td style="padding: 8px 0; color: var(--ueu-muted);">Event Sekolah, Beasiswa, Promosi Komunitas</td>
                        <td style="padding: 8px 0; text-align: right;"><span class="badge badge-red">Tinggi</span></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-weight: 700; color: #f1c40f;">🏛️ Bekasi</td>
                        <td style="padding: 8px 0; color: var(--ueu-muted);">Promosi Digital, Open House, Kerja sama SMA</td>
                        <td style="padding: 8px 0; text-align: right;"><span class="badge badge-yellow">Sedang</span></td>
                    </tr>
                </tbody>
            </table>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


def render_dashboard():
    render_page_header(
        "Dashboard Rekrutmen",
        "Sistem Informasi Geografis Rekrutmen Mahasiswa Baru Universitas Esa Unggul.",
        "Dashboard",
    )

    schools = st.session_state.schools
    alumni = st.session_state.alumni
    visits = st.session_state.visits

    # 5 Metric columns matching design
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.markdown(metric_card("Total Mahasiswa Baru", "8.746", "👥", "+ 12.4%", "dibanding 2019-2023"), unsafe_allow_html=True)
    col2.markdown(metric_card("Asal Sekolah Terdaftar", f"{len(schools):,}", "🎓", "+ 8.7%", "dibanding 2019-2023"), unsafe_allow_html=True)
    col3.markdown(metric_card("Wilayah Terjangkau", "127", "🌐", "+ 6.1%", "dibanding 2019-2023"), unsafe_allow_html=True)
    col4.markdown(metric_card("Rata-rata Aksesibilitas", "68,5", "🚗", "+ 6.2%", "dibanding 2019-2023"), unsafe_allow_html=True)
    col5.markdown(metric_card("Konversi Pendaftaran", "18,7%", "📈", "+ 2.9%", "dibanding 2019-2023"), unsafe_allow_html=True)

    st.markdown('<div class="content-card" style="padding: 16px;">', unsafe_allow_html=True)
    schools_with_zones = render_map_section(compact=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Render Bottom Row Stats and Charts
    render_dashboard_bottom_row(schools_with_zones)

    st.markdown("### Statistik Alumni per Sekolah")
    school_counts = alumni["SCHOOL_NAME"].value_counts().head(6)
    cols = st.columns(3)
    for idx, (school_name, count) in enumerate(school_counts.items()):
        cols[idx % 3].markdown(
            f"<div class='card-box'><strong>{school_name}</strong><br><span>{count} alumni terdaftar</span></div>",
            unsafe_allow_html=True,
        )


def render_map_section(compact: bool = False):
    school_df = st.session_state.schools
    uni_df = st.session_state.universities

    if not compact:
        render_page_header(
            "Peta Rekrutmen Interaktif",
            "Pemetaan sekolah target dan titik kampus UEU untuk prioritas wilayah rekrutmen.",
            "Peta",
        )

    # Calculate zone and distance for all schools
    school_map_with_zones = add_zone_information(school_df, uni_df)

    # Layout: Map (Left) and Information (Right)
    col_map, col_info = st.columns([2.3, 1])

    # Retrieve interactive layer controls from session state
    schools_chk_key = "show_schools_chk_" + str(compact)
    campuses_chk_key = "show_campuses_chk_" + str(compact)
    
    show_schools_layer = st.session_state.get(schools_chk_key, True)
    show_campus_layer = st.session_state.get(campuses_chk_key, True)

    with col_map:
        c_title, c_zone = st.columns([2, 1])
        c_title.markdown("<strong style='font-size:15px; color:var(--ueu-navy-dark);'>Peta Zona Rekrutmen Berdasarkan Titik Pusat Kampus UEU</strong>", unsafe_allow_html=True)
        
        zone_filter = c_zone.selectbox(
            "Tampil Zona",
            options=[
                "Semua Zona",
                "Zona Inti (0 - 5 km)",
                "Zona Potensial (5 - 10 km)",
                "Zona Ekspansi (10 - 15 km)",
                "Zona Perluasan (> 15 km)"
            ],
            key="zone_filter_dropdown_" + str(compact)
        )

        with st.expander("Filter Wilayah & Jenjang Sekolah"):
            f1, f2 = st.columns(2)
            region_filter = f1.selectbox(
                "Wilayah sekolah",
                options=["Semua Wilayah"] + sorted(school_df["PROVINCE"].dropna().unique().tolist()),
                key="region_filter_" + str(compact)
            )
            level_filter = f2.selectbox(
                "Jenjang sekolah",
                options=["Semua Jenjang"] + sorted(school_df["LEVEL"].dropna().unique().tolist()),
                key="level_filter_" + str(compact)
            )

        # Apply filters to school data
        filtered_schools = school_map_with_zones.copy()
        if region_filter != "Semua Wilayah":
            filtered_schools = filtered_schools[filtered_schools["PROVINCE"] == region_filter]
        if level_filter != "Semua Jenjang":
            filtered_schools = filtered_schools[filtered_schools["LEVEL"] == level_filter]

        # Prepare Map Data
        school_map = filtered_schools.copy()
        school_map["DISPLAY_NAME"] = school_map["NAME"]
        school_map["DISPLAY_TYPE"] = "Sekolah"
        
        # Build interactive detailed tooltip details
        school_map["DISPLAY_DETAIL"] = (
            school_map["LEVEL"].fillna("-") + " · " + 
            school_map["DISTRICT"].fillna("-") + "<br/>" +
            "<b>Zone:</b> " + school_map["ZONE"] + " (" + school_map["DISTANCE_TO_CAMPUS"].round(1).astype(str) + " km)"
        )

        uni_map = uni_df.copy()
        uni_map["DISPLAY_NAME"] = uni_map["nama"]
        uni_map["DISPLAY_TYPE"] = "Kampus UEU"
        uni_map["DISPLAY_DETAIL"] = "Universitas Esa Unggul"
        
        # Setup colors and icons for campuses
        def get_uni_color(name):
            n = str(name).lower()
            if "jakarta" in n or "kebon jeruk" in n:
                return [0, 63, 111, 255] # Blue
            elif "tangerang" in n or "citra raya" in n:
                return [32, 198, 107, 255] # Green
            else:
                return [247, 127, 0, 255] # Orange
        uni_map["COLOR"] = uni_map["nama"].apply(get_uni_color)
        uni_map["ICON"] = "🏛️"

        # Define Layers
        # 1. TileLayer - CartoDB Dark Matter (tema gelap, semua marker menyala)
        layers = [
            pdk.Layer(
                "TileLayer",
                data="https://basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png",
                min_zoom=0,
                max_zoom=19,
                tile_size=256,
                opacity=1.0,
            )
        ]

        # 2. Concentric circle overlays (Buffer Zones) di sekitar kampus
        # Radius dalam meter — proporsional untuk zoom level kota
        # Zona Perluasan: 20 km
        if zone_filter == "Semua Zona" or zone_filter == "Zona Perluasan (> 15 km)":
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=uni_map,
                    get_position="[Longitude, Latitude]",
                    get_fill_color="[168, 180, 192, 25]",   # Grey
                    get_line_color="[168, 180, 192, 110]",
                    get_line_width=2,
                    get_radius=20000,  # 20 km
                    pickable=False,
                    stroked=True,
                )
            )
        # Zona Ekspansi: 15 km
        if zone_filter == "Semua Zona" or zone_filter == "Zona Ekspansi (10 - 15 km)":
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=uni_map,
                    get_position="[Longitude, Latitude]",
                    get_fill_color="[44, 130, 201, 30]",      # Blue
                    get_line_color="[44, 130, 201, 140]",
                    get_line_width=2,
                    get_radius=15000,  # 15 km
                    pickable=False,
                    stroked=True,
                )
            )
        # Zona Potensial: 10 km
        if zone_filter == "Semua Zona" or zone_filter == "Zona Potensial (5 - 10 km)":
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=uni_map,
                    get_position="[Longitude, Latitude]",
                    get_fill_color="[255, 211, 42, 35]",    # Yellow
                    get_line_color="[255, 211, 42, 160]",
                    get_line_width=2,
                    get_radius=10000,  # 10 km
                    pickable=False,
                    stroked=True,
                )
            )
        # Zona Inti: 5 km
        if zone_filter == "Semua Zona" or zone_filter == "Zona Inti (0 - 5 km)":
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=uni_map,
                    get_position="[Longitude, Latitude]",
                    get_fill_color="[46, 213, 115, 40]",    # Green
                    get_line_color="[46, 213, 115, 180]",
                    get_line_width=2,
                    get_radius=5000,  # 5 km
                    pickable=False,
                    stroked=True,
                )
            )

        # 3. Add school layer (if checked in legend panel)
        if show_schools_layer and not school_map.empty:
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=school_map,
                    get_position="[Longitude, Latitude]",
                    get_fill_color="ZONE_COLOR",
                    get_radius=350,
                    pickable=True,
                    auto_highlight=True,
                )
            )

        # 4. Add campus layers
        if show_campus_layer and not uni_map.empty:
            # Background colored circle
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=uni_map,
                    get_position="[Longitude, Latitude]",
                    get_fill_color="COLOR",
                    get_line_color="[255, 255, 255]",
                    get_line_width=3,
                    get_radius=650,
                    pickable=True,
                    auto_highlight=True,
                )
            )
            # 🏛️ Emoji text label on top
            layers.append(
                pdk.Layer(
                    "TextLayer",
                    data=uni_map,
                    get_position="[Longitude, Latitude]",
                    get_text="ICON",
                    get_size=18,
                    get_color="[255, 255, 255, 255]",
                    get_alignment_baseline="'center'",
                    get_text_anchor="'middle'",
                )
            )

        # Deck setup
        deck = pdk.Deck(
            map_style=None,
            initial_view_state=pdk.ViewState(
                latitude=-6.2,
                longitude=106.8,
                zoom=9,
                pitch=0,
            ),
            layers=layers,
            tooltip={
                "html": "<b>{DISPLAY_NAME}</b><br/>{DISPLAY_TYPE}<br/>{DISPLAY_DETAIL}",
                "style": {"backgroundColor": "#003f6f", "color": "white", "borderRadius": "5px"},
            },
        )

        st.pydeck_chart(deck)
        
        if not filtered_schools.empty and not compact:
            st.markdown("#### Daftar Sekolah Target")
            st.dataframe(filtered_schools[["NAME", "LEVEL", "DISTRICT", "PROVINCE", "ZONE", "DISTANCE_TO_CAMPUS", "POTENSI_SKOR"]].head(15))

    with col_info:
        # Extract coordinates for UI
        jkt = uni_df[uni_df["nama"].str.contains("Jakarta|Kebon Jeruk", case=False, na=False)]
        tng = uni_df[uni_df["nama"].str.contains("Tangerang|Citra Raya", case=False, na=False)]
        bks = uni_df[uni_df["nama"].str.contains("Bekasi", case=False, na=False)]

        jkt_lat, jkt_lng = (jkt.iloc[0]["Latitude"], jkt.iloc[0]["Longitude"]) if not jkt.empty else (-6.20190, 106.78360)
        tng_lat, tng_lng = (tng.iloc[0]["Latitude"], tng.iloc[0]["Longitude"]) if not tng.empty else (-6.22683, 106.53390)
        bks_lat, bks_lng = (bks.iloc[0]["Latitude"], bks.iloc[0]["Longitude"]) if not bks.empty else (-6.17366, 106.98433)

        # Campus Points Card
        st.markdown(f"""
        <div class="card-box" style="margin-bottom:16px; padding: 14px;">
            <h4 style="margin-top:0; color:var(--ueu-navy-dark); font-size:12px; font-weight:800; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:12px;">Kampus UEU (Titik Pusat)</h4>
            <div style="display:flex; flex-direction:column; gap:12px;">
                <div style="display:flex; align-items:start; gap:10px;">
                    <span style="font-size:18px;">🏛️</span>
                    <div>
                        <strong style="color:#60a5fa; font-size:12px;">Kampus Jakarta</strong><br>
                        <span style="font-size:11px; color:var(--ueu-muted);">Kebon Jeruk, Jakarta Barat<br>Lat: {jkt_lat:.5f} · Lng: {jkt_lng:.5f}</span>
                    </div>
                </div>
                <div style="display:flex; align-items:start; gap:10px;">
                    <span style="font-size:18px;">🏛️</span>
                    <div>
                        <strong style="color:#2ecc71; font-size:12px;">Kampus Tangerang</strong><br>
                        <span style="font-size:11px; color:var(--ueu-muted);">Citra Raya, Tangerang<br>Lat: {tng_lat:.5f} · Lng: {tng_lng:.5f}</span>
                    </div>
                </div>
                <div style="display:flex; align-items:start; gap:10px;">
                    <span style="font-size:18px;">🏛️</span>
                    <div>
                        <strong style="color:#f1c40f; font-size:12px;">Kampus Bekasi</strong><br>
                        <span style="font-size:11px; color:var(--ueu-muted);">Bekasi<br>Lat: {bks_lat:.5f} · Lng: {bks_lng:.5f}</span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Legend and Additional Layers
        st.markdown('<div class="card-box" style="margin-bottom:16px; padding: 14px;">', unsafe_allow_html=True)
        st.markdown('<h4 style="margin-top:0; color:var(--ueu-navy-dark); font-size:12px; font-weight:800; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:12px;">Legenda Peta</h4>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:11px; color:var(--ueu-muted); margin-bottom:8px; font-weight:bold;">ZONA REKRUTMEN (BUFFER)</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="display:flex; flex-direction:column; gap:8px; font-size:12px; margin-bottom:16px;">
            <div style="display:flex; align-items:center; gap:8px;">
                <div style="width:14px; height:14px; background:#2ecc71; border-radius:3px; opacity:0.8;"></div>
                <div>Zona Inti (0 – 5 km)</div>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
                <div style="width:14px; height:14px; background:#f1c40f; border-radius:3px; opacity:0.8;"></div>
                <div>Zona Potensial (5 – 10 km)</div>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
                <div style="width:14px; height:14px; background:#3498db; border-radius:3px; opacity:0.8;"></div>
                <div>Zona Ekspansi (10 – 15 km)</div>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
                <div style="width:14px; height:14px; background:#a8b4c0; border-radius:3px; opacity:0.8;"></div>
                <div>Zona Perluasan (&gt; 15 km)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('<div style="font-size:11px; color:var(--ueu-muted); margin-bottom:8px; font-weight:bold;">LAYER TAMBAHAN</div>', unsafe_allow_html=True)
        st.checkbox("Sebaran Sekolah (SMA/SMK/MA)", value=True, key=schools_chk_key)
        st.checkbox("Kampus UEU", value=True, key=campuses_chk_key)
        st.markdown('</div>', unsafe_allow_html=True)

    # Footer Caption info
    st.markdown(
        '<div style="margin-top:14px; font-size:11px; color:var(--ueu-muted); display:flex; align-items:center; gap:6px;">'
        '<span>ℹ️</span> Zona rekrutmen dihitung berdasarkan jarak (buffer) dari titik pusat masing-masing kampus UEU: '
        'Zona Inti ≤5 km · Zona Potensial 5–10 km · Zona Ekspansi 10–15 km · Zona Perluasan &gt;15 km.'
        '</div>',
        unsafe_allow_html=True
    )

    return school_map_with_zones


def render_school_data():
    render_page_header(
        "Data Sekolah",
        "Manage and analyze recruitment potential from partner and target schools.",
        "Database > School Data Management",
    )

    schools = st.session_state.schools
    alumni = st.session_state.alumni

    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(metric_card("Total Schools", f"{len(schools):,}", "DS", "+ 2.4%"), unsafe_allow_html=True)
    m2.markdown(metric_card("Total Alumni", f"{len(alumni):,}", "AL", "+ 12%"), unsafe_allow_html=True)
    avg_score = schools["POTENSI_SKOR"].mean() if not schools.empty else 0
    m3.markdown(metric_card("Avg. Potensi Skor", f"{avg_score:.1f}", "PS", "High", "priority segment"), unsafe_allow_html=True)
    top_region = schools["DISTRICT"].mode().iloc[0] if not schools.empty else "-"
    m4.markdown(
        f"""
        <div class="metric-card">
            <div class="soft-label">Region Distribution</div>
            <h3>Top: {top_region}</h3>
            <h2 style="font-size:22px;">High Potential</h2>
            <div style="height:8px;background:#1e293b;border-radius:99px;margin-top:12px;">
                <div style="height:8px;width:68%;background:#3b82f6;border-radius:99px;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown("### Import Data Excel")
        excel_school = st.file_uploader("Upload data sekolah (Excel)", type=["xlsx"], key="upload_school")
        if excel_school is not None:
            try:
                imported = pd.read_excel(excel_school)
                required = ["NAME", "LEVEL", "ADDRESS", "PROVINCE", "DISTRICT", "Longitude", "Latitude"]
                if all(col in imported.columns for col in required):
                    imported["POTENSI_SKOR"] = imported.get("POTENSI_SKOR", 70)
                    st.session_state.schools = pd.concat([schools, imported[required + ["POTENSI_SKOR"]]], ignore_index=True)
                    st.success("Data sekolah berhasil diimpor dan ditambahkan.")
                else:
                    st.error("File Excel harus memiliki kolom: {}".format(", ".join(required)))
            except Exception as err:
                st.error(f"Gagal membaca file Excel: {err}")

        excel_alumni = st.file_uploader("Upload data alumni (Excel)", type=["xlsx"], key="upload_alumni")
        if excel_alumni is not None:
            try:
                imported = pd.read_excel(excel_alumni)
                required = ["ALUMNI_NAME", "SCHOOL_NAME", "GRAD_YEAR", "PROGRAM_INTEREST"]
                if all(col in imported.columns for col in required):
                    st.session_state.alumni = pd.concat([alumni, imported[required + ["NOTE"]].fillna("")], ignore_index=True)
                    st.success("Data alumni berhasil diimpor dan ditambahkan.")
                else:
                    st.error("File Excel harus memiliki kolom: {}".format(", ".join(required)))
            except Exception as err:
                st.error(f"Gagal membaca file Excel: {err}")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown("### Template Excel")
        school_template = get_template_school()
        alumni_template = get_template_alumni()
        st.download_button(
            "Unduh Template Data Sekolah",
            data=to_excel_bytes(school_template, sheet_name="Schools"),
            file_name="template_data_sekolah.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.download_button(
            "Unduh Template Data Alumni",
            data=to_excel_bytes(alumni_template, sheet_name="Alumni"),
            file_name="template_data_alumni.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("### Tambah Sekolah Baru")
    with st.form("add_school_form"):
        cols = st.columns(2)
        school_name = cols[0].text_input("Nama Sekolah")
        level = cols[1].selectbox("Jenjang Sekolah", ["Elementary School (SD)", "Junior High School (SMP)", "Senior High School (SMA)"])
        address = st.text_input("Alamat Sekolah")
        province = st.text_input("Provinsi")
        district = st.text_input("Kota / Kabupaten")
        coords = st.columns(2)
        longitude = coords[0].number_input("Longitude", value=106.8, format="%.6f")
        latitude = coords[1].number_input("Latitude", value=-6.2, format="%.6f")
        status = st.selectbox("Status Sekolah", ["Negeri", "Swasta"])
        potential = st.slider("Potensi Skor", 0, 100, 70)
        if st.form_submit_button("Tambah Sekolah"):
            row = {
                "NAME": school_name,
                "LEVEL": level,
                "ADDRESS": address,
                "PROVINCE": province,
                "DISTRICT": district,
                "Longitude": longitude,
                "Latitude": latitude,
                "STATUS": status,
                "POTENSI_SKOR": potential,
            }
            st.session_state.schools = pd.concat([st.session_state.schools, pd.DataFrame([row])], ignore_index=True)
            st.success("Sekolah baru berhasil ditambahkan.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("### Tambah Alumni Baru")
    with st.form("add_alumni_form"):
        cols = st.columns(2)
        alumni_name = cols[0].text_input("Nama Alumni")
        school_name = cols[1].selectbox("Sekolah Asal", options=sorted(st.session_state.schools["NAME"].unique().tolist()))
        grad_year = st.number_input("Tahun Lulus", min_value=2000, max_value=2030, value=2024)
        program_interest = st.text_input("Program Minat")
        note = st.text_area("Catatan")
        if st.form_submit_button("Tambah Alumni"):
            row = {
                "ALUMNI_NAME": alumni_name,
                "SCHOOL_NAME": school_name,
                "GRAD_YEAR": grad_year,
                "PROGRAM_INTEREST": program_interest,
                "NOTE": note,
            }
            st.session_state.alumni = pd.concat([st.session_state.alumni, pd.DataFrame([row])], ignore_index=True)
            st.success("Alumni baru berhasil ditambahkan.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Kelola Data (CRUD)")
    school_tab, alumni_tab, campus_tab = st.tabs(["Sekolah", "Alumni", "Kampus UEU"])

    with school_tab:
        editable_schools = st.session_state.schools.reset_index().rename(columns={"index": "ROW_ID"})
        school_options = [
            f"{row.ROW_ID} - {row.NAME} ({row.DISTRICT})"
            for row in editable_schools.itertuples()
        ]
        if school_options:
            selected_school = st.selectbox("Pilih sekolah untuk update / delete", school_options, key="edit_school_select")
            selected_idx = int(selected_school.split(" - ", 1)[0])
            current = st.session_state.schools.loc[selected_idx]
            with st.form("edit_school_form"):
                cols = st.columns(2)
                updated_name = cols[0].text_input("Nama Sekolah", value=str(current.get("NAME", "")), key="edit_school_name")
                updated_level = cols[1].text_input("Jenjang", value=str(current.get("LEVEL", "")), key="edit_school_level")
                updated_address = st.text_input("Alamat", value=str(current.get("ADDRESS", "")), key="edit_school_address")
                cols = st.columns(2)
                updated_province = cols[0].text_input("Provinsi", value=str(current.get("PROVINCE", "")), key="edit_school_province")
                updated_district = cols[1].text_input("Kota / Kabupaten", value=str(current.get("DISTRICT", "")), key="edit_school_district")
                coords = st.columns(2)
                updated_longitude = coords[0].number_input("Longitude", value=float(current.get("Longitude", 106.8)), format="%.6f", key="edit_school_longitude")
                updated_latitude = coords[1].number_input("Latitude", value=float(current.get("Latitude", -6.2)), format="%.6f", key="edit_school_latitude")
                cols = st.columns(2)
                updated_status = cols[0].text_input("Status", value=str(current.get("STATUS", "Sekolah")), key="edit_school_status")
                updated_score = cols[1].slider("Potensi Skor", 0, 100, int(current.get("POTENSI_SKOR", 70)), key="edit_school_score")
                update_school, delete_school = st.columns(2)
                if update_school.form_submit_button("Update Sekolah", type="primary"):
                    st.session_state.schools.loc[selected_idx, ["NAME", "LEVEL", "ADDRESS", "PROVINCE", "DISTRICT", "Longitude", "Latitude", "STATUS", "POTENSI_SKOR"]] = [
                        updated_name,
                        updated_level,
                        updated_address,
                        updated_province,
                        updated_district,
                        updated_longitude,
                        updated_latitude,
                        updated_status,
                        updated_score,
                    ]
                    st.success("Data sekolah berhasil di-update.")
                if delete_school.form_submit_button("Delete Sekolah"):
                    st.session_state.schools = st.session_state.schools.drop(index=selected_idx).reset_index(drop=True)
                    st.success("Data sekolah berhasil dihapus.")
        else:
            st.info("Belum ada data sekolah.")

    with alumni_tab:
        editable_alumni = st.session_state.alumni.reset_index().rename(columns={"index": "ROW_ID"})
        alumni_options = [
            f"{row.ROW_ID} - {row.ALUMNI_NAME} ({row.SCHOOL_NAME})"
            for row in editable_alumni.itertuples()
        ]
        if alumni_options:
            selected_alumni = st.selectbox("Pilih alumni untuk update / delete", alumni_options, key="edit_alumni_select")
            selected_idx = int(selected_alumni.split(" - ", 1)[0])
            current = st.session_state.alumni.loc[selected_idx]
            with st.form("edit_alumni_form"):
                cols = st.columns(2)
                updated_name = cols[0].text_input("Nama Alumni", value=str(current.get("ALUMNI_NAME", "")), key="edit_alumni_name")
                updated_school = cols[1].text_input("Sekolah Asal", value=str(current.get("SCHOOL_NAME", "")), key="edit_alumni_school")
                updated_year = st.number_input("Tahun Lulus", min_value=2000, max_value=2035, value=int(current.get("GRAD_YEAR", 2024)), key="edit_alumni_year")
                updated_program = st.text_input("Program Minat", value=str(current.get("PROGRAM_INTEREST", "")), key="edit_alumni_program")
                updated_note = st.text_area("Catatan", value=str(current.get("NOTE", "")), key="edit_alumni_note")
                update_alumni, delete_alumni = st.columns(2)
                if update_alumni.form_submit_button("Update Alumni", type="primary"):
                    st.session_state.alumni.loc[selected_idx, ["ALUMNI_NAME", "SCHOOL_NAME", "GRAD_YEAR", "PROGRAM_INTEREST", "NOTE"]] = [
                        updated_name,
                        updated_school,
                        updated_year,
                        updated_program,
                        updated_note,
                    ]
                    st.success("Data alumni berhasil di-update.")
                if delete_alumni.form_submit_button("Delete Alumni"):
                    st.session_state.alumni = st.session_state.alumni.drop(index=selected_idx).reset_index(drop=True)
                    st.success("Data alumni berhasil dihapus.")
        else:
            st.info("Belum ada data alumni.")

    with campus_tab:
        st.caption("Marker oranye pada peta berasal dari data kampus UEU berikut.")
        edited_universities = st.data_editor(
            st.session_state.universities,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "nama": st.column_config.TextColumn("Nama Kampus", required=True),
                "Longitude": st.column_config.NumberColumn("Longitude", format="%.6f", required=True),
                "Latitude": st.column_config.NumberColumn("Latitude", format="%.6f", required=True),
            },
            key="universities_editor",
        )
        save_col, reload_col = st.columns(2)
        if save_col.button("Simpan Kampus ke GeoJSON", type="primary"):
            cleaned = edited_universities.copy()
            cleaned["Longitude"] = pd.to_numeric(cleaned["Longitude"], errors="coerce")
            cleaned["Latitude"] = pd.to_numeric(cleaned["Latitude"], errors="coerce")
            cleaned = cleaned.dropna(subset=["nama", "Longitude", "Latitude"]).reset_index(drop=True)
            st.session_state.universities = cleaned
            save_universities_geojson(cleaned)
            st.success("Data kampus UEU berhasil disimpan ke universitas.geojson.")
        if reload_col.button("Reload dari GeoJSON"):
            load_university_points.clear()
            st.session_state.universities = load_university_points()
            st.success("Data kampus dimuat ulang dari universitas.geojson.")

    st.markdown("### Data Master")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Data Sekolah")
        st.dataframe(st.session_state.schools[["NAME", "LEVEL", "DISTRICT", "PROVINCE", "POTENSI_SKOR"]].head(15))
        if st.button("Export Sekolah ke Excel"):
            st.download_button(
                "Download Sekolah",
                data=to_excel_bytes(st.session_state.schools, sheet_name="Sekolah"),
                file_name="data_sekolah_ueu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    with col2:
        st.markdown("#### Data Alumni")
        st.dataframe(st.session_state.alumni.head(15))
        if st.button("Export Alumni ke Excel"):
            st.download_button(
                "Download Alumni",
                data=to_excel_bytes(st.session_state.alumni, sheet_name="Alumni"),
                file_name="data_alumni_ueu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    st.markdown("---")
    st.markdown("### Alumni Terdaftar per Sekolah")
    summary = st.session_state.alumni.groupby("SCHOOL_NAME").size().reset_index(name="Jumlah Alumni")
    st.dataframe(summary.sort_values(by="Jumlah Alumni", ascending=False).head(20))


def status_style(status: str) -> tuple[str, str, str]:
    normalized = status.lower()
    if "done" in normalized or "completed" in normalized:
        return "green", "done", "var(--ueu-green)"
    if "pending" in normalized or "progress" in normalized:
        return "yellow", "pending", "var(--ueu-yellow)"
    if "follow" in normalized or "urgent" in normalized:
        return "red", "follow", "var(--ueu-red)"
    return "blue", "scheduled", "var(--ueu-navy)"


def render_calendar(visits: pd.DataFrame):
    import datetime

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    first = datetime.date(2024, 10, 1)
    start = first - datetime.timedelta(days=first.weekday())
    cells = [start + datetime.timedelta(days=i) for i in range(28)]

    events_by_date = {}
    for _, row in visits.iterrows():
        try:
            event_date = datetime.date.fromisoformat(str(row["DATE"]))
        except Exception:
            continue
        events_by_date.setdefault(event_date, []).append(row)

    html = ['<div class="calendar-shell"><div class="calendar-grid">']
    for day in days:
        html.append(f'<div class="calendar-head">{day}</div>')
    for day in cells:
        muted = "color:#a2a9b5;" if day.month != 10 else ""
        html.append('<div class="calendar-cell">')
        html.append(f'<div class="calendar-date" style="{muted}">{day.day}</div>')
        for event in events_by_date.get(day, [])[:2]:
            _, event_class, _ = status_style(str(event["STATUS"]))
            html.append(
                f"""
                <div class="calendar-event {event_class}">
                    {event["VISIT_TITLE"]}<br>
                    <span style="font-weight:600;">{event["STATUS"]}</span>
                </div>
                """
            )
        html.append("</div>")
    html.append("</div></div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_marketing_visits():
    render_page_header(
        "Marketing Visits",
        "Manage and track school outreach programs across Jabodetabek.",
        "Recruitment",
    )

    visits = st.session_state.visits

    actions = st.columns([1.8, 1, 1, 0.8])
    search = actions[0].text_input("Search schools by name or location", placeholder="Search schools by name or location...")
    status_groups = ["Scheduled", "In Progress", "Done", "Follow-up Required", "Pending"]
    status_filter = actions[1].selectbox("Status", options=["All"] + status_groups)
    region_filter = actions[2].selectbox("Region", options=["All"] + sorted(visits["REGION"].dropna().unique().tolist()))
    actions[3].button("Add Visit", type="primary", width="stretch")

    filtered_visits = visits.copy()
    if search:
        mask = filtered_visits["VISIT_TITLE"].str.contains(search, case=False, na=False) | filtered_visits["REGION"].str.contains(search, case=False, na=False)
        filtered_visits = filtered_visits[mask]
    if status_filter != "All":
        filtered_visits = filtered_visits[filtered_visits["STATUS"] == status_filter]
    if region_filter != "All":
        filtered_visits = filtered_visits[filtered_visits["REGION"] == region_filter]

    tabs = st.tabs(["Calendar", "Kanban", "Table"])

    with tabs[0]:
        header_cols = st.columns([1, 1])
        header_cols[0].markdown("### October 2024")
        header_cols[1].markdown(
            """
            <div style="text-align:right; padding-top:8px;">
                <span style="color:#20c66b;font-weight:800;">● Done</span>
                <span style="color:#003f6f;font-weight:800;margin-left:16px;">● Scheduled</span>
                <span style="color:#f7c514;font-weight:800;margin-left:16px;">● Pending</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_calendar(filtered_visits)

        k1, k2, k3 = st.columns(3)
        k1.markdown(metric_card("Completed", str((filtered_visits["STATUS"] == "Done").sum()), "OK", "Visits this month", ""), unsafe_allow_html=True)
        k2.markdown(metric_card("Upcoming", str((filtered_visits["STATUS"] == "Scheduled").sum()), "UP", "Confirmed schedule", ""), unsafe_allow_html=True)
        k3.markdown(metric_card("Pending", str((filtered_visits["STATUS"] == "Pending").sum()), "PD", "Awaiting confirmation", ""), unsafe_allow_html=True)

    with tabs[1]:
        columns = st.columns(4)
        kanban_groups = ["Scheduled", "In Progress", "Done", "Follow-up Required"]
        for idx, status in enumerate(kanban_groups):
            with columns[idx]:
                subset = filtered_visits[filtered_visits["STATUS"] == status]
                badge_class, _, color = status_style(status)
                st.markdown(
                    f'<h4><span class="status-dot" style="background:{color};"></span>{status} <span class="badge badge-{badge_class}">{len(subset)}</span></h4>',
                    unsafe_allow_html=True,
                )
                for _, row in subset.iterrows():
                    priority_class = "red" if row["PRIORITY"] == "Urgent" else "yellow" if row["PRIORITY"] == "High" else "blue"
                    st.markdown(
                        f"""
                        <div class="kanban-card">
                            <span class="badge badge-{priority_class}">{row["PRIORITY"]} Priority</span>
                            <strong>{row["VISIT_TITLE"]}</strong>
                            <div style="color:#5f6673; margin-bottom:12px;">{row["REGION"]}</div>
                            <small>{row["DATE"]} · {row["NOTE"]}</small>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    with tabs[2]:
        st.dataframe(filtered_visits, width="stretch", hide_index=True)

    with st.expander("Schedule New Visit"):
        with st.form("add_visit_form"):
            title = st.text_input("Nama Kunjungan / Sekolah")
            region = st.text_input("Wilayah")
            date = st.date_input("Tanggal")
            status = st.selectbox("Status", status_groups)
            priority = st.selectbox("Prioritas", ["High", "Medium", "Low", "Urgent"])
            note = st.text_area("Catatan")
            if st.form_submit_button("Simpan Visit"):
                row = {
                    "VISIT_TITLE": title,
                    "REGION": region,
                    "DATE": date.isoformat(),
                    "STATUS": status,
                    "PRIORITY": priority,
                    "NOTE": note,
                }
                st.session_state.visits = pd.concat([st.session_state.visits, pd.DataFrame([row])], ignore_index=True)
                st.success("Marketing visit berhasil ditambahkan.")


def render_reports():
    render_page_header(
        "Laporan Rekrutmen",
        "Ringkasan angka dan rekomendasi strategi berdasarkan sekolah, alumni, dan agenda marketing.",
        "Reports",
    )

    alumni = st.session_state.alumni
    visit_summary = st.session_state.visits["STATUS"].value_counts().reset_index()
    visit_summary.columns = ["Status", "Jumlah"]
    st.markdown("### Ringkasan Marketing Visits")
    st.dataframe(visit_summary)

    st.markdown("### Rekomendasi Sekolah Potensial")
    top_schools = st.session_state.schools.sort_values(by="POTENSI_SKOR", ascending=False).head(8)
    st.dataframe(top_schools[["NAME", "DISTRICT", "PROVINCE", "POTENSI_SKOR"]], hide_index=True)

    st.markdown("### Alumni per Program Minat")
    if not alumni.empty:
        program_counts = alumni["PROGRAM_INTEREST"].value_counts().reset_index()
        program_counts.columns = ["Program", "Jumlah Alumni"]
        st.dataframe(program_counts)
    else:
        st.info("Belum ada data alumni untuk ditampilkan.")


def main():
    st.set_page_config(
        page_title="UEU Marketing WebGIS",
        page_icon="🎯",
        layout="wide",
    )
    apply_custom_styles()
    init_session_state()
    page = render_sidebar()

    if page == "Dashboard":
        render_dashboard()
    elif page == "Peta Rekrutmen Interaktif":
        render_map_section()
    elif page == "Data Sekolah":
        render_school_data()
    elif page == "Marketing Visits":
        render_marketing_visits()
    elif page == "Laporan":
        render_reports()


if __name__ == "__main__":
    main()
