import difflib
import json
import logging
import re
import string
import sys
from pathlib import Path

import pandas as pd


DATA_DIR = Path("safety-nonsafety")

# Similarity threshold for cross-bucket duplicate detection and fuzzy label
# matching.  Scores strictly greater than this value trigger a match.
SIMILARITY_THRESHOLD = 0.65

# KEYWORD_MAP: maps lowercase keyword patterns found in labels to canonical
# labels. Patterns may be literal substrings or regex-style patterns
# (e.g., ``monitor.*adoption``, ``\bclip\b``). First match wins during
# normalization (checked in insertion order).
KEYWORD_MAP: dict[str, str] = {
    # --- Vehicle Safety ---
    "pit-to-ped": "PIT-pedestrian proximity monitoring",
    "pit to ped": "PIT-pedestrian proximity monitoring",
    "pit–ped": "PIT-pedestrian proximity monitoring",
    "pit/ped": "PIT-pedestrian proximity monitoring",
    "pedestrian proximity": "PIT-pedestrian proximity monitoring",
    "forklift–pedestrian": "PIT-pedestrian proximity monitoring",
    "forklift and pedestrian": "PIT-pedestrian proximity monitoring",
    "pedestrian interaction": "PIT-pedestrian proximity monitoring",
    "pedestrian near-miss": "PIT-pedestrian proximity monitoring",
    "pedestrian collision": "PIT-pedestrian proximity monitoring",
    "pit-to-pit": "PIT-PIT proximity monitoring",
    "pit to pit": "PIT-PIT proximity monitoring",
    "pit–pit": "PIT-PIT proximity monitoring",
    "forklift-to-forklift": "PIT-PIT proximity monitoring",
    "forklift to forklift": "PIT-PIT proximity monitoring",
    "stop-at-intersection": "Intersection stop compliance",
    "stop compliance": "Intersection stop compliance",
    "intersection compliance": "Intersection stop compliance",
    "no-stop": "Intersection stop compliance",
    "end-of-aisle": "Intersection stop compliance",
    "crosswalk compliance": "Intersection stop compliance",
    "forklift speed": "Forklift speed monitoring",
    "pit speed": "Forklift speed monitoring",
    "speeding": "Forklift speed monitoring",
    "obstructed view": "Obstructed-view driving detection",
    "obstructed-view": "Obstructed-view driving detection",
    "forks-first": "Unsafe forklift load handling",
    "bulldozing": "Unsafe forklift load handling",
    "split forking": "Unsafe forklift load handling",
    "load handling": "Unsafe forklift load handling",
    "seatbelt": "Forklift seatbelt compliance",
    "seat belt": "Forklift seatbelt compliance",
    "trailer pull-away": "Trailer pull-away detection",
    "pull-away": "Trailer pull-away detection",
    "dock driver": "Loading dock driver confinement",
    "driver confinement": "Loading dock driver confinement",
    "red light": "Dock red-light compliance",
    "driving direction": "Obstructed-view driving detection",
    "pre-use inspection": "Forklift pre-use inspection compliance",

    # --- Ergonomics ---
    "ergonomic": "Ergonomics risk detection",
    r"\bergo\b": "Ergonomics risk detection",
    "improper bend": "Ergonomics risk detection",
    "overreach": "Ergonomics risk detection",
    "improper lifting": "Ergonomics risk detection",
    "posture risk": "Ergonomics risk detection",

    # --- Hazard Detection ---
    "spill": "Spill and hazard detection",
    "leak detection": "Spill and hazard detection",
    "obstruction": "Obstruction and pathway clearance",
    "blocked walking": "Obstruction and pathway clearance",
    "walkway clearance": "Obstruction and pathway clearance",
    "egress": "Obstruction and pathway clearance",
    "pathway": "Obstruction and pathway clearance",
    "suspended load": "Suspended load / overhead crane safety",
    "overhead crane": "Suspended load / overhead crane safety",
    "working at height": "Working at heights detection",
    "fall protection": "Working at heights detection",
    "harness detection": "Working at heights detection",
    r"\bfire\b": "Fire and environmental hazard detection",
    "machine pinch": "Machine safeguarding detection",
    "hazardous machinery": "Machine safeguarding detection",
    "safety-device circumvention": "Machine safeguarding detection",
    "loto": "LOTO compliance monitoring",
    "lockout": "LOTO compliance monitoring",
    "no-ped zone": "No-pedestrian zone enforcement",
    "no pedestrian zone": "No-pedestrian zone enforcement",
    "no‑pedestrian": "No-pedestrian zone enforcement",
    "no-pedestrian": "No-pedestrian zone enforcement",
    "shortcut hazard": "No-pedestrian zone enforcement",

    # --- PPE Compliance ---
    "ppe": "PPE compliance monitoring",
    "hard hat": "PPE compliance monitoring",
    "safety vest": "PPE compliance monitoring",
    "high-visibility": "PPE compliance monitoring",
    "hi-vis": "PPE compliance monitoring",
    "hairnet": "PPE compliance monitoring",
    "hair net": "PPE compliance monitoring",
    "beard net": "PPE compliance monitoring",
    "safety glasses": "PPE compliance monitoring",
    "glove": "PPE compliance monitoring",
    "bump cap": "PPE compliance monitoring",
    "laceration prevention": "PPE compliance monitoring",

    # --- Loss Prevention ---
    "shrink": "Shrink and loss prevention",
    "theft": "Shrink and loss prevention",
    "unauthorized access": "Unauthorized access detection",
    "security breach": "Unauthorized access detection",
    "restricted zone": "Restricted zone monitoring",
    "restricted area": "Restricted zone monitoring",
    "area control": "Restricted zone monitoring",
    "sensitive-inventory": "Restricted zone monitoring",
    "no-parking zone": "No-parking / no-idling enforcement",
    "no‑parking": "No-parking / no-idling enforcement",
    "no-idling": "No-parking / no-idling enforcement",
    "parking duration": "No-parking / no-idling enforcement",
    "idle time": "No-parking / no-idling enforcement",
    "after-hours": "After-hours presence detection",

    # --- Operational Efficiency ---
    "conveyor": "Conveyor and equipment monitoring",
    "equipment issue": "Conveyor and equipment monitoring",
    "machine shutdown": "Conveyor and equipment monitoring",
    "energy management": "Energy and environmental monitoring",
    "open door": "Door open duration monitoring",
    "door open": "Door open duration monitoring",
    "propped duration": "Door open duration monitoring",
    "dock plate": "Dock equipment compliance",
    "pallet stack": "Pallet optimization",
    "pallet type": "Pallet optimization",
    "product on floor": "Housekeeping and palletization",
    "palletization": "Housekeeping and palletization",
    "housekeeping": "Housekeeping and palletization",
    "productivity": "Operational productivity",
    "staffing": "Operational productivity",
    "shift compliance": "Operational productivity",
    "drone": "Drone-based inspection",
    "remote inspection": "Drone-based inspection",
    "yard gate": "Yard and carrier compliance",
    "carrier compliance": "Yard and carrier compliance",

    # --- Platform Adoption ---
    "training": "Supervisor training and adoption",
    "adoption": "Supervisor training and adoption",
    "onboarding": "Supervisor training and adoption",
    "dashboard": "Dashboard and reporting",
    "reporting": "Dashboard and reporting",
    "executive view": "Dashboard and reporting",
    "executive reporting": "Dashboard and reporting",
    "weekly trend": "Dashboard and reporting",
    "summary view": "Dashboard and reporting",
    r"\bboard\b": "Boards and data visualization",
    "data visualization": "Boards and data visualization",
    "gamif": "Gamification and engagement",
    "leaderboard": "Gamification and engagement",
    "engagement": "Gamification and engagement",
    "usage analytics": "Usage analytics and monitoring",
    "monitor.*adoption": "Usage analytics and monitoring",
    "footage retrieval": "Video footage retrieval",
    "video retrieval": "Video footage retrieval",
    "embed.*video": "Video footage retrieval",
    "incident video": "Video footage retrieval",
    r"\bclip\b": "Video footage retrieval",
    "integration": "System integration",
    "api": "System integration",
    "data export": "System integration",
    r"\bexport\b": "Report export and subscriptions",
    "subscription": "Report export and subscriptions",
    "deep link": "Report export and subscriptions",
    "customer support": "Customer support",
    "troubleshoot": "Customer support",
    "privacy": "Privacy and body blurring",
    "body blur": "Privacy and body blurring",
    "facial recognition": "Identity resolution",
    "identity resolution": "Identity resolution",
    "camera coverage": "Camera scoping and coverage",
    "re-scope": "Camera scoping and coverage",
    "rescop": "Camera scoping and coverage",
    "blind spot": "Camera scoping and coverage",
    "false positive": "Alert accuracy and noise reduction",
    "noise reduction": "Alert accuracy and noise reduction",
    "accuracy": "Alert accuracy and noise reduction",
    "contract": "Commercial and contract management",
    "commercial": "Commercial and contract management",
    "renewal": "Commercial and contract management",
    "rollout": "Enterprise rollout",
    "enterprise": "Enterprise rollout",
    "standardize": "Enterprise rollout",

    # --- Compliance & Monitoring ---
    "heat map": "Heat map analytics",
    "heatmap": "Heat map analytics",
    "hotspot": "Heat map analytics",
    "incident trend": "Incident trend analysis",
    "trend analysis": "Incident trend analysis",
    "trend review": "Incident trend analysis",
    "trend reporting": "Incident trend analysis",
    "trend monitoring": "Incident trend analysis",
    "trend detection": "Incident trend analysis",
    "year-over-year": "Incident trend analysis",
    "leading indicator": "Leading indicator tracking",
    "behavior change": "Leading indicator tracking",
    "impact marker": "Impact measurement and markers",
    "intervention impact": "Impact measurement and markers",
    "change impact": "Impact measurement and markers",
    "quantify impact": "Impact measurement and markers",
    "measure impact": "Impact measurement and markers",
    r"\bmarker\b": "Impact measurement and markers",
    "corrective action": "Action tracking and accountability",
    "action tracking": "Action tracking and accountability",
    "action management": "Action tracking and accountability",
    "action workflow": "Action tracking and accountability",
    "actions workflow": "Action tracking and accountability",
    "assign.*action": "Action tracking and accountability",
    "assign.*track": "Action tracking and accountability",
    "accountability": "Action tracking and accountability",
    "follow-up": "Action tracking and accountability",
    "coaching": "Safety coaching with video",
    "safety coaching": "Safety coaching with video",
    "toolbox talk": "Safety coaching with video",
    "real-time alert": "Real-time alerting",
    "real time alert": "Real-time alerting",
    "sms alert": "Real-time alerting",
    "email alert": "Real-time alerting",
    "near-miss report": "Near-miss reporting",
    "near miss report": "Near-miss reporting",
    "incident investigation": "Incident investigation support",
    "post-incident": "Incident investigation support",
    "video evidence": "Incident investigation support",
    "driver exoneration": "Incident investigation support",
    "timestamp": "Incident investigation support",
    "claims": "Claims and insurance analytics",
    "workers' comp": "Claims and insurance analytics",
    "insurance": "Claims and insurance analytics",
    "business case": "Business case and ROI",
    "roi": "Business case and ROI",
    "sif": "Serious incident / SIF detection",
    "cif": "Serious incident / SIF detection",
    "serious-risk": "Serious incident / SIF detection",
    "benchmarking": "Cross-site benchmarking",
    "benchmark": "Cross-site benchmarking",
    "eye in the sky": "Continuous AI safety coverage",
    "continuous.*coverage": "Continuous AI safety coverage",
    "automated observation": "Continuous AI safety coverage",
    "manual observation": "Continuous AI safety coverage",
    "regulation monitoring": "Regulatory compliance",
    "customs": "Regulatory compliance",
    "federal safety": "Regulatory compliance",
    "compliance and fines": "Regulatory compliance",
    "food hygiene": "PPE compliance monitoring",
    "safe tool use": "Safe tool use",
    "tearing tape": "Safe tool use",
    "pit use compliance": "PIT-pedestrian proximity monitoring",
    "cellphone": "Distracted walking detection",
    "distraction": "Distracted walking detection",
    "fatigue": "Fatigue monitoring (unsupported)",
    "wearable": "Wearable device optimization",
    "iot device": "IoT and supply chain devices",
    "conversational ai": "Conversational AI overlay",
    "service alert": "Customer service alerts",
    "customer service": "Customer service alerts",
    "merchandising": "Merchandising analytics",
    "dwell": "Merchandising analytics",
    "end-cap": "Merchandising analytics",
    "customer-incident": "Customer incident evidence capture",
    "collision/impact": "Collision and impact detection",
    "yellow post": "Collision and impact detection",
    "property damage": "Collision and impact detection",
    "dolly brake": "Dolly and equipment compliance",
    "dolly tongue": "Dolly and equipment compliance",
    "pinch point": "Pinch point risk detection",
    "congestion": "Traffic congestion management",
    "aisle flow": "Traffic congestion management",
    "schedule": "Operational scheduling",
    "planning": "Operational scheduling",
    "leadership": "Stakeholder management",
    "stakeholder": "Stakeholder management",
}

# TAXONOMY: maps each canonical label to exactly one thematic category.
TAXONOMY: dict[str, str] = {
    # Vehicle Safety
    "PIT-pedestrian proximity monitoring": "Vehicle Safety",
    "PIT-PIT proximity monitoring": "Vehicle Safety",
    "Intersection stop compliance": "Vehicle Safety",
    "Forklift speed monitoring": "Vehicle Safety",
    "Obstructed-view driving detection": "Vehicle Safety",
    "Unsafe forklift load handling": "Vehicle Safety",
    "Forklift seatbelt compliance": "Vehicle Safety",
    "Trailer pull-away detection": "Vehicle Safety",
    "Loading dock driver confinement": "Vehicle Safety",
    "Dock red-light compliance": "Vehicle Safety",
    "Forklift pre-use inspection compliance": "Vehicle Safety",

    # Ergonomics
    "Ergonomics risk detection": "Ergonomics",

    # Hazard Detection
    "Spill and hazard detection": "Hazard Detection",
    "Obstruction and pathway clearance": "Hazard Detection",
    "Suspended load / overhead crane safety": "Hazard Detection",
    "Working at heights detection": "Hazard Detection",
    "Fire and environmental hazard detection": "Hazard Detection",
    "Machine safeguarding detection": "Hazard Detection",
    "LOTO compliance monitoring": "Hazard Detection",
    "No-pedestrian zone enforcement": "Hazard Detection",

    # PPE Compliance
    "PPE compliance monitoring": "PPE Compliance",

    # Loss Prevention
    "Shrink and loss prevention": "Loss Prevention",
    "Unauthorized access detection": "Loss Prevention",
    "Restricted zone monitoring": "Loss Prevention",
    "No-parking / no-idling enforcement": "Loss Prevention",
    "After-hours presence detection": "Loss Prevention",

    # Operational Efficiency
    "Conveyor and equipment monitoring": "Operational Efficiency",
    "Energy and environmental monitoring": "Operational Efficiency",
    "Door open duration monitoring": "Operational Efficiency",
    "Dock equipment compliance": "Operational Efficiency",
    "Pallet optimization": "Operational Efficiency",
    "Housekeeping and palletization": "Operational Efficiency",
    "Operational productivity": "Operational Efficiency",
    "Drone-based inspection": "Operational Efficiency",
    "Yard and carrier compliance": "Operational Efficiency",
    "Traffic congestion management": "Operational Efficiency",
    "Operational scheduling": "Operational Efficiency",

    # Platform Adoption
    "Supervisor training and adoption": "Platform Adoption",
    "Dashboard and reporting": "Platform Adoption",
    "Boards and data visualization": "Platform Adoption",
    "Gamification and engagement": "Platform Adoption",
    "Usage analytics and monitoring": "Platform Adoption",
    "Video footage retrieval": "Platform Adoption",
    "System integration": "Platform Adoption",
    "Report export and subscriptions": "Platform Adoption",
    "Customer support": "Platform Adoption",
    "Privacy and body blurring": "Platform Adoption",
    "Identity resolution": "Platform Adoption",
    "Camera scoping and coverage": "Platform Adoption",
    "Alert accuracy and noise reduction": "Platform Adoption",
    "Commercial and contract management": "Platform Adoption",
    "Enterprise rollout": "Platform Adoption",
    "Stakeholder management": "Platform Adoption",

    # Compliance & Monitoring
    "Heat map analytics": "Compliance & Monitoring",
    "Incident trend analysis": "Compliance & Monitoring",
    "Leading indicator tracking": "Compliance & Monitoring",
    "Impact measurement and markers": "Compliance & Monitoring",
    "Action tracking and accountability": "Compliance & Monitoring",
    "Safety coaching with video": "Compliance & Monitoring",
    "Real-time alerting": "Compliance & Monitoring",
    "Near-miss reporting": "Compliance & Monitoring",
    "Incident investigation support": "Compliance & Monitoring",
    "Claims and insurance analytics": "Compliance & Monitoring",
    "Business case and ROI": "Compliance & Monitoring",
    "Serious incident / SIF detection": "Compliance & Monitoring",
    "Cross-site benchmarking": "Compliance & Monitoring",
    "Continuous AI safety coverage": "Compliance & Monitoring",
    "Regulatory compliance": "Compliance & Monitoring",
    "Safe tool use": "Compliance & Monitoring",
    "Distracted walking detection": "Compliance & Monitoring",
    "Fatigue monitoring (unsupported)": "Compliance & Monitoring",
    "Wearable device optimization": "Compliance & Monitoring",
    "IoT and supply chain devices": "Compliance & Monitoring",
    "Conversational AI overlay": "Compliance & Monitoring",
    "Customer service alerts": "Compliance & Monitoring",
    "Merchandising analytics": "Compliance & Monitoring",
    "Customer incident evidence capture": "Compliance & Monitoring",
    "Collision and impact detection": "Compliance & Monitoring",
    "Dolly and equipment compliance": "Compliance & Monitoring",
    "Pinch point risk detection": "Compliance & Monitoring",
}


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def ingest_files(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Read all .json files from *data_dir* and flatten use cases into rows.

    Each row represents one use case with columns:
        file_id, meeting_title, start_time, bucket, label, description,
        evidence, evidence_count

    Files that fail JSON parsing are logged and skipped.  Missing fields are
    handled gracefully (empty strings / empty lists).
    """
    rows: list[dict] = []

    json_files = sorted(data_dir.glob("*.json"))
    if not json_files:
        logger.warning("No .json files found in %s", data_dir)

    for filepath in json_files:
        # --- attempt to parse JSON ---
        try:
            raw = filepath.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Skipping %s: %s", filepath.name, exc)
            continue

        # --- extract file-level metadata ---
        file_id = filepath.stem  # UUID portion of the filename
        meeting_title = data.get("meeting_title", "")
        start_time = data.get("start_time", "")

        extraction = data.get("extraction", {})

        # --- flatten safety and nonsafety use cases ---
        for bucket, key in [
            ("safety", "safety_use_cases"),
            ("nonsafety", "nonsafety_use_cases"),
        ]:
            use_cases = extraction.get(key, [])
            for uc in use_cases:
                evidence = uc.get("evidence", [])
                rows.append(
                    {
                        "file_id": file_id,
                        "meeting_title": meeting_title,
                        "start_time": start_time,
                        "bucket": bucket,
                        "label": uc.get("label", ""),
                        "description": uc.get("description", ""),
                        "evidence": evidence,
                        "evidence_count": len(evidence),
                    }
                )

    df = pd.DataFrame(
        rows,
        columns=[
            "file_id",
            "meeting_title",
            "start_time",
            "bucket",
            "label",
            "description",
            "evidence",
            "evidence_count",
        ],
    )
    return df


# Regex to extract the email domain from speaker strings like "Name <user@domain>"
_SPEAKER_DOMAIN_RE = re.compile(r"<[^@]+@([^>]+)>")


def _classify_speaker(speaker: str | None) -> str:
    """Return 'voxel', 'customer', or 'unknown' for a single speaker string."""
    if speaker is None or not isinstance(speaker, str) or speaker.strip() == "":
        return "unknown"
    m = _SPEAKER_DOMAIN_RE.search(speaker)
    if m is None:
        return "unknown"
    domain = m.group(1).lower()
    if "voxelai.com" in domain:
        return "voxel"
    return "customer"


def classify_speakers(df: pd.DataFrame) -> pd.DataFrame:
    """Add speaker_roles and vendor_only_evidence columns.

    * ``speaker_roles`` — list of role strings (one per evidence item in the row).
    * ``vendor_only_evidence`` — True iff every evidence speaker is "voxel".
      Empty evidence → False (avoids vacuous truth).
    """
    roles_col: list[list[str]] = []
    vendor_only_col: list[bool] = []

    for evidence_list in df["evidence"]:
        if not evidence_list:
            roles_col.append([])
            vendor_only_col.append(False)
            continue
        roles = [_classify_speaker(ev.get("speaker")) for ev in evidence_list]
        roles_col.append(roles)
        vendor_only_col.append(all(r == "voxel" for r in roles))

    df = df.copy()
    df["speaker_roles"] = roles_col
    df["vendor_only_evidence"] = vendor_only_col
    return df


# Punctuation translation table for stripping punctuation from labels.
_PUNCT_TABLE = str.maketrans("", "", string.punctuation)

# Lightweight stopword set for token-overlap checks in duplicate detection.
_STOPWORDS = {
    "and",
    "or",
    "the",
    "a",
    "an",
    "of",
    "for",
    "to",
    "in",
    "on",
    "with",
}


def _strip_label(label: str) -> str:
    """Lowercase and strip punctuation from a label for comparison."""
    return label.lower().translate(_PUNCT_TABLE)


def _tokenize_label(label: str) -> set[str]:
    """Tokenize a label for overlap checks (lowercase, no punctuation/stopwords)."""
    stripped = _strip_label(label)
    return {t for t in stripped.split() if t and t not in _STOPWORDS}


def _labels_match(safety_label: str, nonsafety_label: str, threshold: float) -> tuple[bool, float]:
    """Return whether labels should be treated as duplicates plus a confidence score.

    Primary rule: SequenceMatcher ratio above ``threshold``.
    Fallback rule: strong token overlap (>=2 shared tokens and at least 50%
    overlap relative to the shorter label).
    """
    s_text = _strip_label(safety_label)
    ns_text = _strip_label(nonsafety_label)

    # Direct similarity on normalized strings.
    ratio = difflib.SequenceMatcher(None, s_text, ns_text).ratio()
    if ratio > threshold:
        return True, ratio

    # Containment catches "foo" vs "foo bar" style duplicates.
    if s_text and ns_text and (s_text in ns_text or ns_text in s_text):
        return True, max(ratio, 0.95)

    # Token-overlap fallback for same concept phrased differently.
    s_tokens = _tokenize_label(safety_label)
    ns_tokens = _tokenize_label(nonsafety_label)
    if not s_tokens or not ns_tokens:
        return False, ratio

    shared = s_tokens & ns_tokens
    overlap_ratio = len(shared) / min(len(s_tokens), len(ns_tokens))
    if len(shared) >= 2 and overlap_ratio >= 0.5:
        return True, max(ratio, overlap_ratio)

    return False, ratio


def detect_cross_bucket_duplicates(
    df: pd.DataFrame,
    threshold: float = SIMILARITY_THRESHOLD,
) -> pd.DataFrame:
    """Flag use cases that appear in both safety and nonsafety buckets.

    For each file, compares every safety label against every nonsafety label
    using ``difflib.SequenceMatcher.ratio()`` on lowercased, punctuation-
    stripped text.  A score *strictly greater than* the threshold triggers a
    match.

    Adds two columns:
    * ``cross_bucket_duplicate`` — True if the use case matched across buckets.
    * ``cross_bucket_match`` — ``"matched_label (score)"`` for the best match,
      or None if no match was found.
    """
    # Initialise new columns with defaults.
    dup_flags = [False] * len(df)
    match_info: list[str | None] = [None] * len(df)

    # Build an index-based lookup so we can write back by position.
    for _file_id, group in df.groupby("file_id"):
        safety_idx = group.index[group["bucket"] == "safety"]
        nonsafety_idx = group.index[group["bucket"] == "nonsafety"]

        if len(safety_idx) == 0 or len(nonsafety_idx) == 0:
            continue

        # Track best match per row (highest score).
        best: dict[int, tuple[float, str]] = {}  # idx → (score, original_label)

        for s_i in safety_idx:
            for ns_i in nonsafety_idx:
                s_label = str(df.at[s_i, "label"])
                ns_label = str(df.at[ns_i, "label"])
                is_match, score = _labels_match(s_label, ns_label, threshold)
                if is_match:
                    # Update safety row if this is the best match so far.
                    if s_i not in best or score > best[s_i][0]:
                        best[s_i] = (score, ns_label)

                    # Update nonsafety row if this is the best match so far.
                    if ns_i not in best or score > best[ns_i][0]:
                        best[ns_i] = (score, s_label)

        # Write results back.
        for idx, (score, matched_label) in best.items():
            dup_flags[idx] = True
            match_info[idx] = f"{matched_label} ({score:.2f})"

    df = df.copy()
    df["cross_bucket_duplicate"] = dup_flags
    df["cross_bucket_match"] = match_info
    return df


def normalize_labels(
    df: pd.DataFrame,
    keyword_map: dict[str, str] = KEYWORD_MAP,
    taxonomy: dict[str, str] = TAXONOMY,
) -> pd.DataFrame:
    """Assign a canonical_label and taxonomy_category to every row.

    Three-pass approach:
      Pass 1 — keyword/pattern lookup on the lowercased label against
               *keyword_map*. First match wins (regex-aware).
      Pass 2 — fuzzy-match unmatched labels against canonical labels already
               assigned in Pass 1 using ``SequenceMatcher``.  Assign to the
               best match if the score is strictly above ``SIMILARITY_THRESHOLD``.
      Pass 3 — any remaining labels become their own canonical label and are
               placed in "Other / Uncategorized".
    """
    canonical_col: list[str | None] = [None] * len(df)
    category_col: list[str | None] = [None] * len(df)

    # ------------------------------------------------------------------
    # Pass 1: keyword / phrase lookup (first match wins)
    # ------------------------------------------------------------------
    # Pre-compile keyword patterns.  Entries that contain regex meta-
    # characters (e.g. "monitor.*adoption") are treated as regex; plain
    # strings are escaped and matched as literal substrings.
    _REGEX_META = re.compile(r"[.*+?^${}()|\\]")
    compiled_keywords: list[tuple[re.Pattern, str]] = []
    for keyword, canon in keyword_map.items():
        if _REGEX_META.search(keyword):
            # Treat as regex pattern
            compiled_keywords.append((re.compile(keyword, re.IGNORECASE), canon))
        else:
            # Treat as literal substring (escape for safety)
            compiled_keywords.append(
                (re.compile(re.escape(keyword), re.IGNORECASE), canon)
            )

    for i, label in enumerate(df["label"]):
        lower_label = str(label).lower()
        for pattern, canon in compiled_keywords:
            if pattern.search(lower_label):
                canonical_col[i] = canon
                category_col[i] = taxonomy.get(canon, "Other / Uncategorized")
                break  # first match wins

    # Collect the set of canonical labels assigned so far (for Pass 2).
    assigned_canonical: set[str] = {c for c in canonical_col if c is not None}

    # ------------------------------------------------------------------
    # Pass 2: fuzzy match against already-assigned canonical labels
    # ------------------------------------------------------------------
    if assigned_canonical:
        canonical_list = sorted(assigned_canonical)  # deterministic order
        for i, label in enumerate(df["label"]):
            if canonical_col[i] is not None:
                continue  # already matched in Pass 1
            lower_label = _strip_label(str(label))
            best_score = 0.0
            best_canon: str | None = None
            for canon in canonical_list:
                score = difflib.SequenceMatcher(
                    None, lower_label, _strip_label(canon)
                ).ratio()
                if score > best_score:
                    best_score = score
                    best_canon = canon
            if best_score > SIMILARITY_THRESHOLD and best_canon is not None:
                canonical_col[i] = best_canon
                category_col[i] = taxonomy.get(best_canon, "Other / Uncategorized")

    # ------------------------------------------------------------------
    # Pass 3: remaining labels become their own canonical label
    # ------------------------------------------------------------------
    for i in range(len(df)):
        if canonical_col[i] is None:
            own_label = str(df.iat[i, df.columns.get_loc("label")])
            canonical_col[i] = own_label if own_label else "Unknown"
            category_col[i] = "Other / Uncategorized"

    df = df.copy()
    df["canonical_label"] = canonical_col
    df["taxonomy_category"] = category_col
    return df


# Value-proposition phrases that suggest label inflation — the label makes a
# claim broader than the evidence supports.
_INFLATION_PHRASES = [
    "roi",
    "reduce cost",
    "improve efficiency",
    "drive engagement",
]

# Platform / admin patterns that describe internal workflows rather than
# genuine customer use cases.
_ADMIN_PATTERNS = [
    "training",
    "adoption",
    "footage retrieval",
    "dashboard",
    "reporting",
    "integration",
]


def classify_quality_issues(df: pd.DataFrame) -> pd.DataFrame:
    """Tag each use case with applicable quality issue types.

    Checks five issue categories per row:
      1. ``cross-bucket-duplicate`` — reuses the flag from stage 3.
      2. ``vendor-only-evidence`` — reuses the flag from stage 2.
      3. ``label-inflation`` — label contains value-proposition phrases
         (e.g. "ROI", "reduce cost") without matching evidence.
      4. ``generic-admin`` — label matches platform/admin patterns
         (e.g. "training", "dashboard", "integration").
      5. ``inconsistent-granularity`` — label length is more than 2 standard
         deviations from the median label length in its taxonomy category.

    Adds column: ``quality_issues`` (list of issue-type strings).
    """
    # --- Pre-compute per-category label-length statistics for granularity ---
    label_lengths = df["canonical_label"].str.len()
    category_stats = (
        df.assign(_lbl_len=label_lengths)
        .groupby("taxonomy_category")["_lbl_len"]
        .agg(["median", "std"])
    )

    issues_col: list[list[str]] = []

    for idx, row in df.iterrows():
        issues: list[str] = []

        # 1. cross-bucket-duplicate (from stage 3)
        if row.get("cross_bucket_duplicate", False):
            issues.append("cross-bucket-duplicate")

        # 2. vendor-only-evidence (from stage 2)
        if row.get("vendor_only_evidence", False):
            issues.append("vendor-only-evidence")

        # 3. label-inflation — value-proposition keywords in label
        lower_label = str(row["canonical_label"]).lower()
        if any(phrase in lower_label for phrase in _INFLATION_PHRASES):
            issues.append("label-inflation")

        # 4. generic-admin — platform/admin patterns in label
        if any(pat in lower_label for pat in _ADMIN_PATTERNS):
            issues.append("generic-admin")

        # 5. inconsistent-granularity — label length >2 std devs from
        #    category median
        cat = row["taxonomy_category"]
        if cat in category_stats.index:
            median_len = category_stats.at[cat, "median"]
            std_len = category_stats.at[cat, "std"]
            lbl_len = len(str(row["canonical_label"]))
            # Only flag when std > 0 (avoids division issues / single-member
            # categories where deviation is meaningless).
            if std_len and std_len > 0 and abs(lbl_len - median_len) > 2 * std_len:
                issues.append("inconsistent-granularity")

        issues_col.append(issues)

    df = df.copy()
    df["quality_issues"] = issues_col
    return df


def score_opportunities(df: pd.DataFrame) -> pd.DataFrame:
    """Score and rank non-safety (and safety-adjacent) canonical labels.

    Only canonical labels with at least one nonsafety-bucket row are included.
    Each label is scored as:
        score = call_count * 2 + customer_evidence_count - quality_issue_count

    Returns a DataFrame sorted by score descending with columns:
        canonical_label, taxonomy_category, call_count,
        customer_evidence_count, quality_issue_count, score,
        representative_quotes
    """
    # --- Filter to canonical labels that have at least one nonsafety row ---
    nonsafety_labels = set(
        df.loc[df["bucket"] == "nonsafety", "canonical_label"].unique()
    )
    if not nonsafety_labels:
        return pd.DataFrame(
            columns=[
                "canonical_label",
                "taxonomy_category",
                "call_count",
                "customer_evidence_count",
                "quality_issue_count",
                "score",
                "representative_quotes",
            ]
        )

    # Work with all rows for qualifying canonical labels (both buckets)
    mask = df["canonical_label"].isin(nonsafety_labels)
    subset = df[mask]

    records: list[dict] = []

    for canon, grp in subset.groupby("canonical_label"):
        # taxonomy_category — take the first (should be consistent)
        taxonomy_cat = grp["taxonomy_category"].iloc[0]

        # call_count — distinct file_ids mentioning this canonical label
        call_count = grp["file_id"].nunique()

        # customer_evidence_count — total evidence items from "customer" speakers
        customer_evidence_count = 0
        customer_quotes: list[str] = []

        for _, row in grp.iterrows():
            evidence_list = row.get("evidence", [])
            speaker_roles = row.get("speaker_roles", [])
            for ev, role in zip(evidence_list, speaker_roles):
                if role == "customer":
                    customer_evidence_count += 1
                    quote = ev.get("quote", "")
                    if quote and len(customer_quotes) < 3:
                        customer_quotes.append(quote)

        # quality_issue_count — total quality issue tags across all rows
        quality_issue_count = sum(len(issues) for issues in grp["quality_issues"])

        # Score formula
        score = call_count * 2 + customer_evidence_count - quality_issue_count

        records.append(
            {
                "canonical_label": canon,
                "taxonomy_category": taxonomy_cat,
                "call_count": call_count,
                "customer_evidence_count": customer_evidence_count,
                "quality_issue_count": quality_issue_count,
                "score": score,
                "representative_quotes": customer_quotes,
            }
        )

    result = pd.DataFrame(records)
    result = result.sort_values("score", ascending=False).reset_index(drop=True)
    return result

def main() -> None:
    """Run the analysis pipeline."""
    logger.info("Starting Voxel analysis pipeline")

    # Ingest
    df = ingest_files()
    logger.info("Ingested %d use-case rows from %d files",
                len(df), df["file_id"].nunique())
    print(f"Total rows ingested: {len(df)}")

    # Classify speaker roles
    df = classify_speakers(df)
    vendor_only_count = df["vendor_only_evidence"].sum()
    logger.info("Speaker classification complete — %d vendor-only rows",
                vendor_only_count)

    # Detect cross-bucket duplicates
    df = detect_cross_bucket_duplicates(df)
    dup_count = df["cross_bucket_duplicate"].sum()
    logger.info("Cross-bucket duplicate detection complete — %d duplicates",
                dup_count)

    # Normalize labels into taxonomy
    df = normalize_labels(df)
    n_canonical = df["canonical_label"].nunique()
    n_other = (df["taxonomy_category"] == "Other / Uncategorized").sum()
    logger.info("Label normalization complete — %d canonical labels, %d uncategorized rows",
                n_canonical, n_other)

    # Classify quality issues
    df = classify_quality_issues(df)
    issue_rows = sum(1 for issues in df["quality_issues"] if issues)
    logger.info("Quality issue classification complete — %d rows with issues",
                issue_rows)

    # Score and rank non-safety opportunities
    opportunities_df = score_opportunities(df)
    logger.info("Opportunity scoring complete — %d ranked labels",
                len(opportunities_df))
    if not opportunities_df.empty:
        top = opportunities_df.iloc[0]
        logger.info("Top opportunity: %s (score %d)", top["canonical_label"], top["score"])



if __name__ == "__main__":
    main()
