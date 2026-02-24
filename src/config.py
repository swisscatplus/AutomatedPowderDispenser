'''Config file for the "Automated Powder Dispenser" APD'''
#!/usr/bin/env python3

# BEC - November 2025 
# Constants to be changed for APD
#-------------------------------------------------------------------------------

import os

#-------------------------------------------------------------------------------
# Base paths
#-------------------------------------------------------------------------------
# Absolute path of the project directory (where this config.py lives)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_CONFIG = {
    "base_directory": BASE_DIR,                     # project root
    "soft_directory": os.path.join(BASE_DIR, "soft"),
    "data_directory": os.path.join(BASE_DIR, "data"),
    "log_app_directory": os.path.join(BASE_DIR, "log"),
    "measures_directory": os.path.join(BASE_DIR, "data", "Measures"),

    # Log / cleanup policies
    "cleanup_old_files": False,
    "days_before_cleanup": 7,
    "log_rotation_days": 20,

    # UI / application meta
    "window_title": "Automated Powder Dispenser - APD_v1",
}

#-------------------------------------------------------------------------------
# Mettler scale (WebService, XPR/XSR/Q3)
#-------------------------------------------------------------------------------
SCALE_CONFIG = {
    # HTTP (81) or HTTPS (444)
    "scheme": "http",                     # "http" or "https"
    "ip": "192.168.0.50",
    "port": 81,                           # 81 for HTTP, 444 for HTTPS

    # Path to the WSDL file (made relative to the project root)
    # "wsdl_path": os.path.join(
    #     BASE_DIR,
    #     "documents",
    #     "Mettler",
    #     "MT.Laboratory.Balance.XprXsr.V03.wsdl",
    # ),
    "wsdl_path": r"MT.Laboratory.Balance.XprXsr.V03.wsdl",


    # Password used to decrypt the SessionId returned by OpenSession
    "password": "SWISSCAT",

    # HTTPS certificate verification:
    #   - False         → no verification (or HTTP)
    #   - "path/to.cer" → custom CA bundle
    "verify": False,

    # Network / WebService behavior
    "timeout_s": 8,
    "autoconnect": True,                  # try to connect automatically at startup
    "watch_period_ms": 5000,              # heartbeat period in WinBalance

    # Doors (DraftShieldsService.SetPosition)
    "door_ids": ["LeftOuter"],
    "open_width": 100,
    "close_width": 0,

    # Pan sensing thresholds
    # Minimum gross mass to consider that a vial is present on the pan
    "vial_presence_min_mg": 14000.0,

    # Thresholds and sampling parameters used for "Is empty ?"
    "empty_threshold_mg": 9.0,            # default threshold in mg for is_pan_empty
    "empty_samples": 10,
    "empty_sleep_s": 0.05,
}

#-------------------------------------------------------------------------------
# UR3 robot
#-------------------------------------------------------------------------------
UR3_CONFIG = {
    "ip": "192.168.0.5",
    "script_port": 30002,
    "dashboard_port": 29999,

    # SFTP listing of .urp programs
    "sftp_port": 22,
    "sftp_user": "root",
    "sftp_password": "swisscat",
    "programs_dir": "/programs",          # standard root on UR e-Series

    # RTDE registers
    #  - rtde_input_register: GPii[n] used for VialsNB
    #  - disp_rtde_input_register: GPii[n] used for DispNB
    "rtde_input_register": 20,
    "disp_rtde_input_register": 21,

    # Mapping from logical vial IDs (E1-1, E2-3, ...) to the integer sent to VialsNB
    "vial_id_to_number": {
        "E1-1": 4,  "E1-2": 3,  "E1-3": 2,  "E1-4": 1,
        "E2-1": 7,  "E2-2": 6,  "E2-3": 5,
        "E3-1": 11, "E3-2": 10, "E3-3": 9,  "E3-4": 8,
    },

    # Optional: default .urp program paths used by Auto / JSON modes
    "programs": {
        "P1": "/programs/00Main/P1Bastien.urp",
        "P2": "/programs/00Main/P2Bastien.urp",
        "P3": "/programs/00Main/P3Bastien.urp",
        "P4": "/programs/00Main/P4Bastien.urp",
    },

    # Heartbeat / polling periods used in WinRobotArm
    "watch_period_ms": 3000,              # connection heartbeat
    "run_poll_ms": 700,                   # when a program is running
}

#-------------------------------------------------------------------------------
# Storage (powder dispensers layout & labels)
#-------------------------------------------------------------------------------
STORAGE_CONFIG = {
    # Logical IDs available
    "ids": ["S1", "S2", "S3", "S4"],

    # Visual order of slots in the 2x2 UI (Top-Left, Top-Right, Bottom-Left, Bottom-Right)
    "order": ["S3", "S4", "S1", "S2"],

    # Mapping logical ID → number written to DispNB (UR3 RTDE)
    "id_to_number": {
        "S1": 1,
        "S2": 2,
        "S3": 3,
        "S4": 4,
    },

    # Human-readable labels shown in the Storage panel and used by JSON / P4 lookup
    "labels": {
        "S1": "Pow1",
        "S2": "Pow2",
        "S3": "Pow3",
        "S4": "Pow4",
    },
}