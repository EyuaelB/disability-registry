"""Crosswalk between this registry's enums and the SPDCI Disability Registry code
directories (CD.DR.01 - CD.DR.15, plus the CD.COM lists the DR objects reuse).

THE ONE PLACE the standard's vocabulary is spelled out. Both DCI templates carry
a generated copy of these tables (between the BEGIN/END GENERATED markers) —
regenerate with ``./scripts/generate-dci-crosswalk.py`` after editing this file;
``test/test_dci_crosswalk.py`` fails the build if the copies drift, and renders
every standard value through both templates to prove it survives the round trip.

Why a table and not keyword matching: the previous templates guessed with
substring tests ("'RECEIVED' in s"), which filed the standard's "Received, but
not enough" as fully received — the unmet need this registry exists to report
vanished at the interface. A table either knows a value or it does not.

Shape of each list::

    "LIST": {
        "cd": "CD.DR.05 SupportStatusEnum",      # where the standard defines it
        "standard": [                              # the standard's own values, in order
            ("0", "Required", "REQUIRED"),         # (code, label, enum that represents it)
            ...
        ],
        "outbound": {"RECEIVING": "Received"},     # enums with no own standard value
        "aliases": {"NEEDED": "REQUIRED"},         # extra inbound spellings -> enum
        "fallback": "OTHER",                       # inbound value that matches nothing
    }

Inbound matching normalises the incoming text (upper case, punctuation stripped,
spaces to underscores) and looks up, in order: the standard label, the standard
code, the enum name, an alias. Outbound emits the standard LABEL (the standard's
own examples use labels, not numeric codes).
"""

from __future__ import annotations

import re

_NORMALISE_DROP = re.compile(r"[^A-Z0-9_]")


def normalise(value) -> str:
    """Canonical key for inbound matching. Mirrored in Jinja by the ``norm`` macro
    the generator writes into the templates — keep the two identical."""
    text = "" if value is None else str(value)
    text = text.strip().upper().replace("-", "_").replace(" ", "_").replace("/", "_")
    return _NORMALISE_DROP.sub("", text)


CROSSWALK: dict[str, dict] = {
    # ── DO.DR.05 support objects ──────────────────────────────────────────
    "SUPPORT_STATUS": {
        "cd": "CD.DR.05 SupportStatusEnum",
        "standard": [
            ("0", "Required", "REQUIRED"),
            ("1", "Received", "RECEIVED"),
            ("2", "Received, but not enough", "PARTIALLY_RECEIVED"),
            ("3", "Not required", "NOT_REQUIRED"),
        ],
        # RECEIVING is a received support that is still being delivered; the
        # standard has no separate word for it. DISCONTINUED is not counted as
        # unmet by utils/support_summary.py, so it must not read as Required.
        "outbound": {"RECEIVING": "Received", "DISCONTINUED": "Not required"},
        "aliases": {
            "NEEDED": "REQUIRED", "NEED": "REQUIRED", "REQUIRES": "REQUIRED",
            "PARTIAL": "PARTIALLY_RECEIVED", "PARTIALLY_RECEIVED": "PARTIALLY_RECEIVED",
            "INSUFFICIENT": "PARTIALLY_RECEIVED", "NOT_ENOUGH": "PARTIALLY_RECEIVED",
            "RECEIVING": "RECEIVING", "DISCONTINUED": "DISCONTINUED", "STOPPED": "DISCONTINUED",
            "NOT_NEEDED": "NOT_REQUIRED",
        },
        "fallback": None,
    },
    "SUPPORT_FREQUENCY": {
        "cd": "CD.DR.04 SupportFrequency",
        "standard": [
            ("1", "Permanent", "PERMANENT"),
            ("2", "Daily", "DAILY"),
            ("3", "Weekly", "WEEKLY"),
            ("4", "Occasional", "OCCASIONAL"),
            ("5", "None", "NONE"),
        ],
        "outbound": {"MONTHLY": "Occasional", "AS_NEEDED": "Occasional", "TEMPORARY": "Occasional"},
        "aliases": {"CONTINUOUS": "PERMANENT", "MONTHLY": "MONTHLY", "AS_NEEDED": "AS_NEEDED",
                    "ON_DEMAND": "AS_NEEDED", "TEMPORARY": "TEMPORARY"},
        "fallback": None,
    },
    "HUMAN_ASSISTANCE_TYPE": {
        "cd": "CD.DR.03 HumanAssistanceType",
        "standard": [
            ("basic_activity", "basic_activity", "PERSONAL_CARE"),
            ("mobility", "mobility", "MOBILITY"),
            ("communication", "communication", "COMMUNICATION"),
            ("decision_making", "decision_making", "DECISION_MAKING_SUPPORT"),
            ("multiple", "multiple", "MULTIPLE"),
        ],
        # Finer registry types the standard groups under one of its five.
        "outbound": {
            "SIGN_LANGUAGE_INTERPRETATION": "communication",
            "DOMESTIC_SUPPORT": "basic_activity",
            "MEDICAL_SUPPORT": "basic_activity",
            "EDUCATIONAL_SUPPORT": "multiple",
            "EMPLOYMENT_SUPPORT": "multiple",
            "FINANCIAL_MANAGEMENT": "decision_making",
            "SUPERVISION": "decision_making",
            "OTHER": "multiple",
        },
        "aliases": {
            "PERSONAL_CARE": "PERSONAL_CARE", "BASIC_DAILY_LIVING": "PERSONAL_CARE",
            "SIGN_LANGUAGE": "SIGN_LANGUAGE_INTERPRETATION", "INTERPRETATION": "SIGN_LANGUAGE_INTERPRETATION",
            "DOMESTIC": "DOMESTIC_SUPPORT", "HOUSEHOLD": "DOMESTIC_SUPPORT",
            "MEDICAL": "MEDICAL_SUPPORT", "NURSING": "MEDICAL_SUPPORT",
            "EDUCATION": "EDUCATIONAL_SUPPORT", "EMPLOYMENT": "EMPLOYMENT_SUPPORT",
            "FINANCIAL": "FINANCIAL_MANAGEMENT", "SUPPORTED_DECISION_MAKING": "DECISION_MAKING_SUPPORT",
        },
        "fallback": "OTHER",
    },
    "ASSISTIVE_TECHNOLOGY_TYPE": {
        "cd": "CD.DR.06 AssistiveTechnologyEnum (WHO Priority Assistive Products List)",
        "standard": [
            ("5", "Cane/stick", "CANES"),
            ("11", "Crutches, auxiliary/elbow", "CRUTCHES"),
            ("3", "Braille displays (note takers)", "BRAILLE_DEVICES"),
            ("9", "Communication boards/books/cards", "COMMUNICATION_BOARDS"),
            ("8", "Club foot brace", "ORTHOSES"),
            ("wheelchair_manual", "Wheelchairs, manual", "MANUAL_WHEELCHAIR"),
            ("wheelchair_electric", "Wheelchairs, electrically powered", "ELECTRIC_WHEELCHAIR"),
            ("walking_frames", "Walking frames/walkers", "WALKING_FRAMES"),
            ("prostheses", "Prostheses, lower limb", "PROSTHESES"),
            ("footwear", "Therapeutic footwear", "THERAPEUTIC_FOOTWEAR"),
            ("hearing_aids", "Hearing aids (digital) and batteries", "HEARING_AIDS"),
            ("spectacles", "Spectacles", "SPECTACLES"),
            ("magnifiers", "Magnifiers, optical", "MAGNIFIERS"),
            ("screen_readers", "Screen readers", "SCREEN_READERS"),
            ("speech_devices", "Communication software", "SPEECH_GENERATING_DEVICES"),
            ("cushions", "Pressure relief cushions", "PRESSURE_RELIEF_CUSHIONS"),
            ("incontinence", "Incontinence products, absorbent", "INCONTINENCE_PRODUCTS"),
            ("cochlear", "Cochlear implants", "COCHLEAR_IMPLANTS"),
            ("other", "Other", "OTHER"),
        ],
        "outbound": {},
        "aliases": {
            "CANE": "CANES", "WHITE_CANE": "CANES", "STICK": "CANES", "CANE_STICK": "CANES",
            "CRUTCH": "CRUTCHES", "CRUTCHES": "CRUTCHES",
            "WALKER": "WALKING_FRAMES", "WALKING_FRAME": "WALKING_FRAMES", "ROLLATOR": "WALKING_FRAMES",
            "WHEELCHAIR": "MANUAL_WHEELCHAIR", "POWERED_WHEELCHAIR": "ELECTRIC_WHEELCHAIR",
            "PROSTHESIS": "PROSTHESES", "ORTHOSIS": "ORTHOSES", "BRACE": "ORTHOSES",
            "HEARING_AID": "HEARING_AIDS", "GLASSES": "SPECTACLES", "EYEGLASSES": "SPECTACLES",
            "MAGNIFIER": "MAGNIFIERS", "BRAILLE": "BRAILLE_DEVICES", "BRAILLERS": "BRAILLE_DEVICES",
            "BRAILLE_WRITING_EQUIPMENTBRAILLERS": "BRAILLE_DEVICES",
            "SCREEN_READER": "SCREEN_READERS", "COMMUNICATION_BOARD": "COMMUNICATION_BOARDS",
            "SPEECH_GENERATING_DEVICE": "SPEECH_GENERATING_DEVICES",
            "CUSHION": "PRESSURE_RELIEF_CUSHIONS", "DEAF_BLIND_COMMUNICATORS": "SPEECH_GENERATING_DEVICES",
        },
        "fallback": "OTHER",
    },
    "MEDICAL_CARE_TYPE": {
        "cd": "CD.DR.11 MedicalCareEnum",
        "standard": [
            ("1", "Maintenance medicine", "MAINTENANCE_MEDICINE"),
            ("2", "Rehabilitation", "REHABILITATION"),
            ("3", "Specialised health care", "SPECIALISED_HEALTH_CARE"),
        ],
        "outbound": {
            "PHYSIOTHERAPY": "Rehabilitation", "OCCUPATIONAL_THERAPY": "Rehabilitation",
            "SPEECH_THERAPY": "Rehabilitation",
            "PSYCHIATRIC_CARE": "Specialised health care", "PSYCHOLOGICAL_COUNSELLING": "Specialised health care",
            "DIALYSIS": "Specialised health care", "REGULAR_SPECIALIST_REVIEW": "Specialised health care",
            "SURGERY": "Specialised health care", "WOUND_CARE": "Specialised health care",
            "RESPIRATORY_SUPPORT": "Specialised health care", "NUTRITION_SUPPORT": "Specialised health care",
            "OTHER": "Specialised health care",
        },
        "aliases": {
            "MEDICINE": "MAINTENANCE_MEDICINE", "MEDICATION": "MAINTENANCE_MEDICINE", "DRUGS": "MAINTENANCE_MEDICINE",
            "SPECIALIZED_HEALTH_CARE": "SPECIALISED_HEALTH_CARE", "SPECIALIST_CARE": "SPECIALISED_HEALTH_CARE",
            "PHYSIOTHERAPY": "PHYSIOTHERAPY", "PHYSIO": "PHYSIOTHERAPY",
            "OCCUPATIONAL_THERAPY": "OCCUPATIONAL_THERAPY", "SPEECH_THERAPY": "SPEECH_THERAPY",
            "PSYCHIATRIC_CARE": "PSYCHIATRIC_CARE", "PSYCHOLOGICAL_COUNSELLING": "PSYCHOLOGICAL_COUNSELLING",
            "COUNSELLING": "PSYCHOLOGICAL_COUNSELLING", "DIALYSIS": "DIALYSIS",
            "REGULAR_SPECIALIST_REVIEW": "REGULAR_SPECIALIST_REVIEW", "SURGERY": "SURGERY",
            "WOUND_CARE": "WOUND_CARE", "RESPIRATORY_SUPPORT": "RESPIRATORY_SUPPORT",
            "OXYGEN": "RESPIRATORY_SUPPORT", "NUTRITION_SUPPORT": "NUTRITION_SUPPORT",
        },
        "fallback": "OTHER",
    },
    "HOUSING_SUPPORT_TYPE": {
        "cd": "CD.DR.12 HousingSupportEnum",
        "standard": [
            ("1", "Home adaptation", "HOME_ADAPTATION"),
            ("2", "Relocation to accessible housing as home adaptation not feasible", "RELOCATION"),
            ("3", "Significant utility costs", "UTILITY_COST_SUPPORT"),
        ],
        "outbound": {
            "RAMP_INSTALLATION": "Home adaptation", "HANDRAILS": "Home adaptation",
            "BATHROOM_MODIFICATION": "Home adaptation", "DOOR_WIDENING": "Home adaptation",
            "HOME_REPAIR": "Home adaptation",
            "GROUND_FLOOR_ALLOCATION": "Relocation to accessible housing as home adaptation not feasible",
            "ACCESSIBLE_SOCIAL_HOUSING": "Relocation to accessible housing as home adaptation not feasible",
            "ASSISTED_LIVING_FACILITY": "Relocation to accessible housing as home adaptation not feasible",
            "RESIDENTIAL_CARE": "Relocation to accessible housing as home adaptation not feasible",
            "RENT_SUBSIDY": "Significant utility costs",
            "OTHER": "Home adaptation",
        },
        "aliases": {
            "RELOCATION": "RELOCATION", "RELOCATE": "RELOCATION", "REHOUSING": "RELOCATION",
            "UTILITY_COSTS": "UTILITY_COST_SUPPORT", "UTILITIES": "UTILITY_COST_SUPPORT",
            "RAMP": "RAMP_INSTALLATION", "RAMP_INSTALLATION": "RAMP_INSTALLATION", "HANDRAILS": "HANDRAILS",
            "GRAB_RAILS": "HANDRAILS", "BATHROOM_MODIFICATION": "BATHROOM_MODIFICATION",
            "DOOR_WIDENING": "DOOR_WIDENING", "GROUND_FLOOR_ALLOCATION": "GROUND_FLOOR_ALLOCATION",
            "RENT_SUBSIDY": "RENT_SUBSIDY", "ACCESSIBLE_SOCIAL_HOUSING": "ACCESSIBLE_SOCIAL_HOUSING",
            "ASSISTED_LIVING_FACILITY": "ASSISTED_LIVING_FACILITY", "RESIDENTIAL_CARE": "RESIDENTIAL_CARE",
            "HOME_REPAIR": "HOME_REPAIR",
        },
        "fallback": "OTHER",
    },
    "ANIMAL_ASSISTANCE_TYPE": {
        "cd": "CD.DR.13 AnimalAssistanceEnum",
        "standard": [
            ("1", "Service dog (guide, signal..)", "GUIDE_DOG"),
            ("2", "Therapy animal", "THERAPY_ANIMAL"),
            ("3", "Other", "OTHER"),
        ],
        "outbound": {
            "HEARING_DOG": "Service dog (guide, signal..)", "ALERT_DOG": "Service dog (guide, signal..)",
            "MOBILITY_ASSISTANCE_DOG": "Service dog (guide, signal..)",
            "PSYCHIATRIC_SERVICE_DOG": "Service dog (guide, signal..)",
            "SEIZURE_RESPONSE_DOG": "Service dog (guide, signal..)",
        },
        "aliases": {
            "SERVICE_DOG": "GUIDE_DOG", "GUIDE_DOG": "GUIDE_DOG", "SIGNAL_DOG": "HEARING_DOG",
            "HEARING_DOG": "HEARING_DOG", "ALERT_DOG": "ALERT_DOG",
            "MOBILITY_ASSISTANCE_DOG": "MOBILITY_ASSISTANCE_DOG", "PSYCHIATRIC_SERVICE_DOG": "PSYCHIATRIC_SERVICE_DOG",
            "SEIZURE_RESPONSE_DOG": "SEIZURE_RESPONSE_DOG",
        },
        "fallback": "OTHER",
    },
    # ── DO.DR.04 DisabilityDetails ────────────────────────────────────────
    "IMPAIRMENT_TYPE": {
        "cd": "CD.DR.01 ImpairmentType / Functional LimitationType (options 1 and 2)",
        "standard": [
            # Option 1 (impairment)
            ("1", "Seeing", "VISUAL"),
            ("2", "Hearing", "HEARING"),
            ("3", "Voice and speech", "SPEECH_LANGUAGE"),
            ("4", "Physical and movement related functions", "PHYSICAL_MOBILITY"),
            ("5", "Intellectual", "INTELLECTUAL"),
            ("6", "Mental (psycho-social)", "PSYCHOSOCIAL"),
            ("7", "Others (skin, cardiovascular, respiratory, digestive systems)", "CHRONIC_ILLNESS"),
            ("8", "Multiple", "MULTIPLE"),
            # Option 2 (functional limitation, Washington Group domains)
            ("opt2_3", "Communication", "SPEECH_LANGUAGE"),
            ("opt2_4", "Mobility", "PHYSICAL_MOBILITY"),
            ("opt2_5", "Cognition", "INTELLECTUAL"),
            ("opt2_6", "Interpersonal interaction and relationship", "PSYCHOSOCIAL"),
            ("opt2_7", "Self-care", "SELF_CARE"),
            ("opt2_8", "Others", "OTHER"),
        ],
        "outbound": {"DEAFBLIND": "Multiple", "NEUROLOGICAL": "Others (skin, cardiovascular, respiratory, digestive systems)",
                     "LEARNING": "Intellectual"},
        "aliases": {
            "VISION": "VISUAL", "VISUAL": "VISUAL", "BLIND": "VISUAL", "SIGHT": "VISUAL",
            "DEAF": "HEARING", "DEAFBLIND": "DEAFBLIND", "DEAF_BLIND": "DEAFBLIND",
            "SPEECH": "SPEECH_LANGUAGE", "LANGUAGE": "SPEECH_LANGUAGE", "VOICE": "SPEECH_LANGUAGE",
            "PHYSICAL": "PHYSICAL_MOBILITY", "WALKING": "PHYSICAL_MOBILITY", "LOCOMOTOR": "PHYSICAL_MOBILITY",
            "COGNITIVE": "INTELLECTUAL", "LEARNING": "LEARNING", "MENTAL": "PSYCHOSOCIAL",
            "PSYCHOSOCIAL": "PSYCHOSOCIAL", "MENTAL_HEALTH": "PSYCHOSOCIAL",
            "NEUROLOGICAL": "NEUROLOGICAL", "CHRONIC_ILLNESS": "CHRONIC_ILLNESS", "CHRONIC": "CHRONIC_ILLNESS",
            "SELFCARE": "SELF_CARE", "OTHER": "OTHER",
        },
        "fallback": "OTHER",
    },
    "IMPAIRMENT_LEVEL": {
        # The registry keeps the 4-point Washington Group scale (it is what censuses
        # and the Ethiopia country pack use). The standard has 5 points; "Moderate"
        # has no WG equivalent and is read as SOME_DIFFICULTY.
        "cd": "CD.DR.02 ImpairmentLevel / Functional LimitationsLevel",
        "standard": [
            ("1", "No impairment or difficulty", "NO_DIFFICULTY"),
            ("2", "Mild impairment or difficulty", "SOME_DIFFICULTY"),
            ("4", "Severe impairment or difficulty", "A_LOT_OF_DIFFICULTY"),
            ("5", "Complete impairment or difficulty", "CANNOT_DO_AT_ALL"),
        ],
        "outbound": {},
        "aliases": {
            "MODERATE_IMPAIRMENT_OR_DIFFICULTY": "SOME_DIFFICULTY", "3": "SOME_DIFFICULTY",
            "MODERATE": "SOME_DIFFICULTY", "MILD": "SOME_DIFFICULTY", "SOME": "SOME_DIFFICULTY",
            "NONE": "NO_DIFFICULTY", "NO": "NO_DIFFICULTY",
            "SEVERE": "A_LOT_OF_DIFFICULTY", "A_LOT": "A_LOT_OF_DIFFICULTY",
            "COMPLETE": "CANNOT_DO_AT_ALL", "UNABLE": "CANNOT_DO_AT_ALL", "CANNOT": "CANNOT_DO_AT_ALL",
            "PROFOUND": "CANNOT_DO_AT_ALL",
        },
        "fallback": None,
    },
    "IMPAIRMENT_CAUSE": {
        "cd": "CD.DR.08 ImpairmentCause / FunctionalLimitationCause",
        "standard": [
            ("0", "Birth congenital", "CONGENITAL"),
            ("1", "Birth complication", "MEDICAL_COMPLICATION"),
            ("2", "Illness", "ILLNESS"),
            ("3", "Domestic accident", "OTHER_ACCIDENT"),
            ("4", "Road accident", "ROAD_ACCIDENT"),
            ("5", "Work accident", "WORK_ACCIDENT"),
            ("6", "Violence", "CONFLICT_VIOLENCE"),
            ("7", "Armed conflict", "CONFLICT_VIOLENCE"),
            ("8", "Ageing", "AGEING"),
        ],
        "outbound": {"NATURAL_DISASTER": "Domestic accident", "UNKNOWN": "", "OTHER": ""},
        "aliases": {
            "CONGENITAL": "CONGENITAL", "BIRTH": "CONGENITAL", "BIRTH_DEFECT": "CONGENITAL",
            "DISEASE": "ILLNESS", "SICKNESS": "ILLNESS", "ACCIDENT": "OTHER_ACCIDENT",
            "TRAFFIC_ACCIDENT": "ROAD_ACCIDENT", "OCCUPATIONAL_ACCIDENT": "WORK_ACCIDENT",
            "WAR": "CONFLICT_VIOLENCE", "CONFLICT": "CONFLICT_VIOLENCE", "AGING": "AGEING",
            "OLD_AGE": "AGEING", "NATURAL_DISASTER": "NATURAL_DISASTER", "DISASTER": "NATURAL_DISASTER",
            "MEDICAL_COMPLICATION": "MEDICAL_COMPLICATION", "UNKNOWN": "UNKNOWN",
        },
        "fallback": "OTHER",
    },
    "AGE_ONSET": {
        # DO.DR.04 age_on_set is this CODE LIST in the standard, not a number.
        "cd": "CD.DR.07 DisabilityOnSet",
        "standard": [
            ("0", "Born with", "AT_BIRTH"),
            ("1", "Childhood", "CHILDHOOD_6_12"),
            ("2", "Working age", "ADULTHOOD_18_59"),
            ("3", "Old age", "OLD_AGE_60_PLUS"),
        ],
        "outbound": {"EARLY_CHILDHOOD_0_5": "Childhood", "ADOLESCENCE_13_17": "Childhood", "UNKNOWN": ""},
        "aliases": {"BIRTH": "AT_BIRTH", "SINCE_BIRTH": "AT_BIRTH", "CONGENITAL": "AT_BIRTH",
                    "CHILD": "CHILDHOOD_6_12", "ADULT": "ADULTHOOD_18_59", "ADULTHOOD": "ADULTHOOD_18_59",
                    "ELDERLY": "OLD_AGE_60_PLUS"},
        "fallback": None,
    },
    # ── DO.DR.03 PersonwithDisability ─────────────────────────────────────
    "DISABILITY_STATUS": {
        # Outbound derivation (Approved vs Expired) uses certificate_expiry_date;
        # see the template. This table covers the words themselves.
        "cd": "CD.DR.14 DisabilityStatus",
        "standard": [
            ("1", "Approved", "ASSESSED_DISABLED"),
            ("2", "Pending approval", "PENDING_ASSESSMENT"),
            ("3", "Expired", "EXPIRED"),
        ],
        "outbound": {"ASSESSED_NOT_DISABLED": "", "SELF_DECLARED": "Pending approval", "UNKNOWN": ""},
        "aliases": {
            "ASSESSED_DISABLED": "ASSESSED_DISABLED", "DISABLED": "ASSESSED_DISABLED", "YES": "ASSESSED_DISABLED",
            "TRUE": "ASSESSED_DISABLED", "ACTIVE": "ASSESSED_DISABLED", "VALID": "ASSESSED_DISABLED",
            "PENDING": "PENDING_ASSESSMENT", "UNDER_REVIEW": "PENDING_ASSESSMENT",
            "ASSESSED_NOT_DISABLED": "ASSESSED_NOT_DISABLED", "NOT_DISABLED": "ASSESSED_NOT_DISABLED",
            "NO": "ASSESSED_NOT_DISABLED", "FALSE": "ASSESSED_NOT_DISABLED", "REJECTED": "ASSESSED_NOT_DISABLED",
            "SELF_DECLARED": "SELF_DECLARED", "LAPSED": "EXPIRED", "UNKNOWN": "UNKNOWN",
        },
        "fallback": "UNKNOWN",
    },
    "DISABILITY_STATUS_LEVEL": {
        "cd": "CD.DR.15 DisabilityStatusLevel",
        "standard": [
            ("1", "High support needs", "PROFOUND"),
            ("2", "Severe", "SEVERE"),
            ("3", "Moderate", "MODERATE"),
            ("4", "Mild", "MILD"),
        ],
        "outbound": {"NONE": ""},
        "aliases": {"PROFOUND": "PROFOUND", "VERY_SEVERE": "PROFOUND", "NONE": "NONE"},
        "fallback": None,
    },
    "TRANSPORT_REQUIREMENT": {
        "cd": "CD.DR.9 TransportRequirement",
        "standard": [
            ("1", "Public transportation", "ACCESSIBLE_PUBLIC_TRANSPORT"),
            ("2", "Point-to-point transportation", "ESCORTED_TRAVEL"),
            ("3", "Adapted vehicle", "ADAPTED_VEHICLE"),
        ],
        "outbound": {
            "WHEELCHAIR_ACCESSIBLE_VEHICLE": "Adapted vehicle",
            "AMBULANCE_TRANSPORT": "Point-to-point transportation",
            "TRANSPORT_ALLOWANCE": "Public transportation",
            "NONE": "", "OTHER": "",
        },
        "aliases": {
            "PUBLIC_TRANSPORT": "ACCESSIBLE_PUBLIC_TRANSPORT", "PUBLIC": "ACCESSIBLE_PUBLIC_TRANSPORT",
            "POINT_TO_POINT": "ESCORTED_TRAVEL", "DOOR_TO_DOOR": "ESCORTED_TRAVEL", "ESCORTED": "ESCORTED_TRAVEL",
            "WHEELCHAIR_ACCESSIBLE_VEHICLE": "WHEELCHAIR_ACCESSIBLE_VEHICLE", "AMBULANCE": "AMBULANCE_TRANSPORT",
            "AMBULANCE_TRANSPORT": "AMBULANCE_TRANSPORT", "TRANSPORT_ALLOWANCE": "TRANSPORT_ALLOWANCE",
            "ALLOWANCE": "TRANSPORT_ALLOWANCE", "NONE": "NONE",
        },
        "fallback": "OTHER",
    },
    "HOUSING_TYPE": {
        "cd": "CD.DR.10 HousingType",
        "standard": [
            ("1", "Own home/rent", "INDEPENDENT_HOME"),
            ("2", "Living in relatives' home", "FAMILY_HOME"),
            ("3", "Social housing", "SOCIAL_HOUSING"),
            ("4", "Care institution", "RESIDENTIAL_INSTITUTION"),
        ],
        "outbound": {
            "SUPPORTED_LIVING": "Social housing", "GROUP_HOME": "Care institution",
            "HOSPITAL_LONG_STAY": "Care institution", "TEMPORARY_SHELTER": "", "HOMELESS": "", "OTHER": "",
        },
        "aliases": {
            "OWN_HOME": "INDEPENDENT_HOME", "RENT": "INDEPENDENT_HOME", "RENTED": "INDEPENDENT_HOME",
            "INDEPENDENT": "INDEPENDENT_HOME", "RELATIVES_HOME": "FAMILY_HOME", "FAMILY": "FAMILY_HOME",
            "WITH_RELATIVES": "FAMILY_HOME", "INSTITUTION": "RESIDENTIAL_INSTITUTION",
            "CARE_HOME": "RESIDENTIAL_INSTITUTION", "SUPPORTED_LIVING": "SUPPORTED_LIVING",
            "GROUP_HOME": "GROUP_HOME", "HOSPITAL": "HOSPITAL_LONG_STAY", "SHELTER": "TEMPORARY_SHELTER",
            "HOMELESS": "HOMELESS", "STREET": "HOMELESS",
        },
        "fallback": "OTHER",
    },
    # ── Shared (CD.COM) lists the DR objects reuse ────────────────────────
    "SEX": {
        "cd": "CD.COM.03 sex",
        "standard": [
            ("male", "male", "MALE"),
            ("female", "female", "FEMALE"),
            ("other", "other", "OTHERS"),
            ("unknown", "unknown", "UNKNOWN"),
        ],
        "outbound": {},
        "aliases": {"M": "MALE", "F": "FEMALE", "OTHERS": "OTHERS", "O": "OTHERS", "U": "UNKNOWN"},
        "fallback": "UNKNOWN",
    },
    "RELATIONSHIP": {
        # HL7 v3 RoleCode family codes. GUARDIAN has no HL7 code; it travels as
        # the standard's nearest word and is kept exact through its own alias.
        "cd": "CD.COM.07 relationship_type",
        "standard": [
            ("SPS", "SPS", "SPOUSE"),
            ("PRN", "PRN", "PARENT"),
            ("CHILD", "CHILD", "CHILD"),
            ("SIB", "SIB", "SIBLING"),
            ("GRPRN", "GRPRN", "GRANDPARENT"),
            ("GRNDCHILD", "GRNDCHILD", "GRANDCHILD"),
            ("FAMMEMB", "FAMMEMB", "OTHER_RELATIVE"),
            ("SIGOTHR", "SIGOTHR", "NON_RELATIVE"),
        ],
        "outbound": {"GUARDIAN": "GUARDIAN"},
        "aliases": {
            "HUSB": "SPOUSE", "WIFE": "SPOUSE", "HUSBAND": "SPOUSE", "DOMPART": "SPOUSE", "SPOUSE": "SPOUSE",
            "MTH": "PARENT", "FTH": "PARENT", "MOTHER": "PARENT", "FATHER": "PARENT", "PARENT": "PARENT",
            "ADOPTP": "PARENT", "STPPRN": "PARENT",
            "SON": "CHILD", "DAU": "CHILD", "SONC": "CHILD", "DAUC": "CHILD", "DAUGHTER": "CHILD",
            "NCHILD": "CHILD", "STPCHLD": "CHILD", "CHLDADOPT": "CHILD", "CHLDFOST": "CHILD",
            "BRO": "SIBLING", "SIS": "SIBLING", "BROTHER": "SIBLING", "SISTER": "SIBLING",
            "HSIB": "SIBLING", "NSIB": "SIBLING", "STPSIB": "SIBLING", "SIBLING": "SIBLING",
            "GRFTH": "GRANDPARENT", "GRMTH": "GRANDPARENT", "GRANDPARENT": "GRANDPARENT",
            "GRANDFATHER": "GRANDPARENT", "GRANDMOTHER": "GRANDPARENT",
            "GRNDSON": "GRANDCHILD", "GRNDDAU": "GRANDCHILD", "GRANDCHILD": "GRANDCHILD",
            "EXT": "OTHER_RELATIVE", "AUNT": "OTHER_RELATIVE", "UNCLE": "OTHER_RELATIVE",
            "COUSN": "OTHER_RELATIVE", "NIENEPH": "OTHER_RELATIVE", "INLAW": "OTHER_RELATIVE",
            "RELATIVE": "OTHER_RELATIVE", "OTHER_RELATIVE": "OTHER_RELATIVE",
            "GUARDIAN": "GUARDIAN", "FRIEND": "NON_RELATIVE", "NEIGHBOUR": "NON_RELATIVE",
            "ASSOCIATE": "NON_RELATIVE", "NON_RELATIVE": "NON_RELATIVE",
        },
        "fallback": "NON_RELATIVE",
    },
    "CAREGIVER_RELATIONSHIP": {
        "cd": "CD.COM.07 relationship_type (DO.DR.06 relationship)",
        "standard": [
            ("SPS", "SPS", "SPOUSE"),
            ("PRN", "PRN", "PARENT"),
            ("CHILD", "CHILD", "CHILD"),
            ("SIB", "SIB", "SIBLING"),
            ("FAMMEMB", "FAMMEMB", "OTHER_RELATIVE"),
            ("SIGOTHR", "SIGOTHR", "FRIEND"),
        ],
        "outbound": {"NEIGHBOUR": "SIGOTHR", "PAID_CAREGIVER": "", "COMMUNITY_VOLUNTEER": "",
                     "INSTITUTION": "", "OTHER": ""},
        "aliases": {
            "HUSB": "SPOUSE", "WIFE": "SPOUSE", "SPOUSE": "SPOUSE", "MTH": "PARENT", "FTH": "PARENT",
            "PARENT": "PARENT", "SON": "CHILD", "DAU": "CHILD", "BRO": "SIBLING", "SIS": "SIBLING",
            "SIBLING": "SIBLING", "EXT": "OTHER_RELATIVE", "GRPRN": "OTHER_RELATIVE", "GRNDCHILD": "OTHER_RELATIVE",
            "RELATIVE": "OTHER_RELATIVE", "OTHER_RELATIVE": "OTHER_RELATIVE", "FRIEND": "FRIEND",
            "NEIGHBOUR": "NEIGHBOUR", "NEIGHBOR": "NEIGHBOUR", "PAID": "PAID_CAREGIVER",
            "PAID_CAREGIVER": "PAID_CAREGIVER", "PROFESSIONAL": "PAID_CAREGIVER",
            "VOLUNTEER": "COMMUNITY_VOLUNTEER", "COMMUNITY_VOLUNTEER": "COMMUNITY_VOLUNTEER",
            "INSTITUTION": "INSTITUTION",
        },
        "fallback": "OTHER",
    },
}


def outbound_map(name: str) -> dict[str, str]:
    """enum value -> standard label (first standard entry per enum wins)."""
    spec = CROSSWALK[name]
    out: dict[str, str] = {}
    for _code, label, enum in spec["standard"]:
        out.setdefault(enum, label)
    for enum, label in spec["outbound"].items():
        out.setdefault(enum, label)
    return out


def inbound_map(name: str) -> dict[str, str]:
    """normalised inbound text -> enum value.

    Precedence: standard label, standard code, enum name, alias. A later source
    never overrides an earlier one, so a standard label always wins.
    """
    spec = CROSSWALK[name]
    inbound: dict[str, str] = {}
    for _code, label, enum in spec["standard"]:
        inbound.setdefault(normalise(label), enum)
    for code, _label, enum in spec["standard"]:
        inbound.setdefault(normalise(code), enum)
    for enum in set(e for _c, _l, e in spec["standard"]) | set(spec["outbound"]):
        inbound.setdefault(normalise(enum), enum)
    for alias, enum in spec["aliases"].items():
        inbound.setdefault(normalise(alias), enum)
    inbound.pop("", None)
    return inbound


def fallbacks() -> dict[str, str]:
    return {name: (spec["fallback"] or "") for name, spec in CROSSWALK.items()}
