#!/usr/bin/env python3

# BEC - November 2025
# Automated Powder Dispenser (APD) – Mettler WebService backend (XPR/XSR/Q3).
#-------------------------------------------------------------------------------
#  deviceScale.py – WebService client and façade for the laboratory balance.
#
#  FILE STRUCTURE
#  ────────────────────────────────────────────────────────────────────────────
#  [0] Imports & Config
#  [1] Crypto: decrypt SessionId (OpenSession)
#  [2] Common infra: zeep serialization, session-retry decorator, helpers
#  [3] Class _WMWebService: WebService implementation
#      3.1  Session
#      3.2  Draft shields (doors): single _drive_doors policy
#      3.3  Standby / UI poke
#      3.4  Weighing: Zero / Tare / GetWeight(s) (single core)
#      3.5  Pan sensing: is_pan_empty / is_pan_present
#      3.6  Methods & Tolerances (WeighingTask) compact helpers
#      3.7  Dosing (simple job) & Dosing Head read/write
#      3.8  Notifications (simple option A)
#  [4] WM facade (public API for the UI)
#-------------------------------------------------------------------------------

from __future__ import annotations
from typing import Optional, List, Callable, Dict
import time
import threading

from config import SCALE_CONFIG

# ─────────────────────────────────────────────────────────────────────────────
# [0] Imports & Config (zeep / crypto)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from zeep import Client, Settings
    from zeep.transports import Transport
    from zeep.helpers import serialize_object as _zeep_serialize
except Exception:
    Client = Settings = Transport = None
    _zeep_serialize = None

try:
    from base64 import b64decode
    from cryptography.hazmat.primitives import hashes, padding
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except Exception:
    PBKDF2HMAC = Cipher = None


def _need(modname: str):
    """Raise a runtime error indicating a missing required module."""
    raise RuntimeError(f"Module requis manquant : {modname}. Installe : pip install {modname}")


# ─────────────────────────────────────────────────────────────────────────────
# [1] Crypto: decrypt SessionId (OpenSession)
# ─────────────────────────────────────────────────────────────────────────────
def _decrypt_session_id(password: str, enc_b64: str, salt_b64: str) -> str:
    """
    Decrypt the SessionId returned by OpenSession.

    Crypto scheme:
    - AES-256 in ECB mode
    - Key derived via PBKDF2-HMAC-SHA1, 1000 iterations, salt from the service.
    """
    if PBKDF2HMAC is None:
        _need("cryptography")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA1(), length=32, salt=b64decode(salt_b64), iterations=1000)
    key = kdf.derive(password.encode("utf-8"))
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    dec = cipher.decryptor().update(b64decode(enc_b64)) + cipher.decryptor().finalize()
    unpad = padding.PKCS7(128).unpadder()
    data = unpad.update(dec) + unpad.finalize()
    return data.decode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# [2] Common infra: serialization, retry decorator, value/unit parsing
# ─────────────────────────────────────────────────────────────────────────────
def _serialize(obj):
    """
    Best-effort conversion of a zeep object to plain Python types (dict, list,
    primitives). If zeep is unavailable, returns the original object.
    """
    if _zeep_serialize is None:
        return obj  # raw fallback (may still contain zeep objects)
    try:
        return _zeep_serialize(obj)
    except Exception:
        return obj


def _with_session_retry(fn):
    """
    Decorator which guarantees an open Session:

    - Ensures a valid session before the call
    - If an exception mentioning "Session" is raised, reopens the session
      once and retries the call.
    """
    def _w(self, *a, **k):
        self._ensure_session()
        try:
            return fn(self, *a, **k)
        except Exception as e:
            if "Session" in str(e):
                self._open_session()
                return fn(self, *a, **k)
            raise
    _w.__name__ = fn.__name__
    return _w


def _soap(self, svc_method, **payload):
    """
    Call the given zeep service method with the provided payload and serialize
    the result (when possible) into plain Python types.
    """
    resp = svc_method(**payload)
    return _serialize(resp)


def _dig(obj, *keys):
    """
    Tolerant nested access helper for dicts / objects.

    Example
    -------
    _dig(r, "A", "B") works like r["A"]["B"] or r.A.B, depending on
    whether `r` is a dict or a zeep object.
    """
    cur = obj
    for k in keys:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            cur = getattr(cur, k, None)
    return cur


def _read_vu(node):
    """
    Read a (value, unit) pair from a ValueWithUnit-like node.

    Handles both:
    - dicts with keys 'ValueWithUnit' or 'Value' / 'Unit'
    - zeep objects with attributes ValueWithUnit / Value / Unit
    """
    if not node:
        return None, None
    if isinstance(node, dict):
        vwu = node.get("ValueWithUnit")
        if vwu is not None and isinstance(vwu, dict):
            return vwu.get("Value"), vwu.get("Unit")
        return node.get("Value"), node.get("Unit")
    # zeep object
    vwu = getattr(node, "ValueWithUnit", None)
    if vwu is not None:
        return getattr(vwu, "Value", None), getattr(vwu, "Unit", None)
    return getattr(node, "Value", None), getattr(node, "Unit", None)


def _to_float(s):
    """Convert a string/number to float, accepting comma as decimal separator."""
    try:
        return float(str(s).replace(",", "."))
    except Exception:
        return None


def _to_g(val, unit):
    """
    Convert a value + unit into grams.

    Supported units:
    - g / gram / gramme / grams
    - mg / milligram / milligramme
    - kg / kilogram / kilogramme

    Returns
    -------
    float or None
        Converted value in grams, or None if conversion is not possible.
    """
    if val is None or unit is None:
        return None
    v = _to_float(val)
    if v is None:
        return None
    u = str(unit).strip().lower()
    if u in ("g", "gram", "gramme", "grams"):
        return v
    if u in ("mg", "milligram", "milligramme"):
        return v / 1000.0
    if u in ("kg", "kilogram", "kilogramme"):
        return v * 1000.0
    return None


def _ws_unit(u: Optional[str]) -> str:
    """
    Map a short/locale unit string to the WebService expected unit name.

    Examples
    --------
    "g"           -> "Gram"
    "mg"          -> "Milligram"
    "kg"          -> "Kilogram"
    "%", "percent" -> "Percent"
    """
    if not u:
        return "Gram"
    s = str(u).strip().lower()
    return {
        "g": "Gram", "gram": "Gram", "gramme": "Gram", "grams": "Gram",
        "mg": "Milligram", "milligram": "Milligram", "milligramme": "Milligram",
        "kg": "Kilogram", "kilogram": "Kilogram", "kilogramme": "Kilogram",
        "%": "Percent", "percent": "Percent", "pourcent": "Percent", "percentage": "Percent",
    }.get(s, u)


# ─────────────────────────────────────────────────────────────────────────────
# [3] WebService implementation
# ─────────────────────────────────────────────────────────────────────────────
class _WMWebService:
    """
    Low-level WebService backend for XPR/XSR/Q3 balances.

    Responsibilities:
    - Session management
    - Draft shields (doors) control
    - Standby/wakeup
    - Weighing & pan sensing
    - Methods & tolerances (WeighingTask)
    - Dosing jobs & dosing head read/write
    - Notifications polling (dosing automation)
    """
    TNS = "http://MT/Laboratory/Balance/XprXsr/V03"

    def __init__(self, cfg: dict):
        if Client is None:
            _need("zeep")

        scheme = cfg.get("scheme", "http")
        ip = cfg.get("ip", "192.168.0.50")
        port = int(cfg.get("port", 81))
        wsdl = cfg["wsdl_path"]

        self.password = cfg["password"]
        self.verify = cfg.get("verify", False)
        self.timeout_s = int(cfg.get("timeout_s", 8))
        self.door_ids: List[str] = cfg.get("door_ids") or ["LeftOuter", "RightOuter"]
        self.open_width: int = int(cfg.get("open_width", 113))
        self.close_width: int = int(cfg.get("close_width", 0))
        self._method_name: str = cfg.get("method_name", "General Weighing")

        self.base = f"{scheme}://{ip}:{port}/MT/Laboratory/Balance/XprXsr/V03/"

        import requests
        self._session = requests.Session()
        self._session.verify = self.verify
        self._transport = Transport(session=self._session, timeout=self.timeout_s)

        self._client = Client(
            wsdl, settings=Settings(strict=False, xml_huge_tree=True), transport=self._transport
        )
        ns = f"{{{self.TNS}}}"

        # Service bindings
        self._svc_basic = self._client.create_service(ns + "BasicHttpBinding_IBasicService", self.base)
        self._svc_dosing = self._client.create_service(ns + "BasicHttpBinding_IDosingAutomationService", self.base)
        self._svc_draft = self._client.create_service(ns + "BasicHttpBinding_IDraftShieldsService", self.base)
        self._svc_notify = self._client.create_service(ns + "BasicHttpBinding_INotificationService", self.base)
        self._svc_session = self._client.create_service(ns + "BasicHttpBinding_ISessionService", self.base)
        self._svc_weigh = self._client.create_service(ns + "BasicHttpBinding_IWeighingService", self.base)
        self._svc_wtask = self._client.create_service(ns + "BasicHttpBinding_IWeighingTaskService", self.base)

        self.session_id: Optional[str] = None
        self._task_ready: bool = False
        self._last_async_cmd_id: Optional[int] = None

    # ─────────────────────────────────────────────────────────────────────────
    # 3.1 Session
    # ─────────────────────────────────────────────────────────────────────────
    def _open_session(self):
        """Open a new WebService session and decrypt the SessionId."""
        resp = _soap(self, self._svc_session.OpenSession)
        enc_id = (resp or {}).get("SessionId")
        salt = (resp or {}).get("Salt")
        if not enc_id or not salt:
            raise RuntimeError("OpenSession: SessionId ou Salt manquant")
        self.session_id = _decrypt_session_id(self.password, enc_id, salt)
        self._task_ready = False

    def _ensure_session(self):
        """Ensure a valid SessionId is present, opening a session if needed."""
        if not self.session_id:
            self._open_session()

    def connect(self):
        """Public entry point used by WM: ensure an open session."""
        self._ensure_session()

    def close(self):
        """Forget the current SessionId without trying to close it server-side."""
        self.session_id = None
        self._task_ready = False

    def is_connected(self) -> bool:
        """Return True if a SessionId is currently stored, False otherwise."""
        return bool(self.session_id)

    # ─────────────────────────────────────────────────────────────────────────
    # 3.2 Draft shields (doors) — single policy
    # ─────────────────────────────────────────────────────────────────────────
    def _set_all_doors(self, width: int):
        """
        Send a SetPosition command for all configured draft shields with
        the same opening width.
        """
        req = {
            "SessionId": self.session_id,
            "DraftShieldsPositions": {
                "DraftShieldPosition": [
                    {"DraftShieldId": d, "OpeningWidth": int(width)} for d in self.door_ids
                ]
            },
        }
        _ = _soap(self, self._svc_draft.SetPosition, **req)

    def _draft_positions(self) -> Dict[str, int]:
        """
        Read current opening widths for all configured draft shields.

        Returns
        -------
        dict[str, int]
            Mapping DraftShieldId -> OpeningWidth.
        """
        if not self.door_ids:
            return {}
        resp = _soap(
            self,
            self._svc_draft.GetPosition,
            SessionId=self.session_id,
            DraftShieldIds={"DraftShieldIdentifier": list(self.door_ids)},
        )
        info = (resp or {}).get("DraftShieldsInformation") or {}
        items = info.get("DraftShieldInformation") or []
        if not isinstance(items, (list, tuple)):
            items = [items]
        out: Dict[str, int] = {}
        for it in items:
            did = (it or {}).get("DraftShieldId")
            w = (it or {}).get("OpeningWidth")
            if did is None or w is None:
                continue
            try:
                out[str(did)] = int(w)
            except Exception:
                v = _to_float(w)
                if v is not None:
                    out[str(did)] = int(v)
        return out

    def _verify_door(self, expect_width: int, tol: int = 2, timeout_s: float = 2.0) -> bool:
        """
        Poll door positions until the expected width is observed within tolerance
        or until timeout is reached.
        """
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            pos = self._draft_positions()
            if pos and all(abs(pos.get(d, -9999) - expect_width) <= tol for d in self.door_ids):
                return True
            time.sleep(0.05)
        return False

    @_with_session_retry
    def _drive_doors(self, target_width: int, label: str, tol: int = 2) -> str:
        """
        Robust high-level door movement:

        1) Direct SetPosition + verify
        2) If it fails: WakeupFromStandby + retry
        3) If it still fails: small "poke" on SOAP UI + retry
        4) If everything fails: raise RuntimeError
        """
        # 1) direct attempt
        self._set_all_doors(target_width)
        if self._verify_door(target_width, tol=tol):
            return "OK"

        # 2) Deep standby → wakeup then retry
        self.wakeup_from_standby()
        self._set_all_doors(target_width)
        if self._verify_door(target_width, tol=tol):
            return "OK (after WakeupFromStandby)"

        # 3) Sleepy UI / SOAP stack → small "nudge" then retry
        self._poke_display()
        self._set_all_doors(target_width)
        if self._verify_door(target_width, tol=tol):
            return "OK (after nudge)"

        # 4) Clear failure
        raise RuntimeError(f"{label}: mouvement non observé (veille/UI/verrouillage ?)")

    def open_door(self) -> str:
        """Open all configured draft shields using the unified door policy."""
        return self._drive_doors(self.open_width, "Open door")

    def close_door(self) -> str:
        """Close all configured draft shields using the unified door policy."""
        return self._drive_doors(self.close_width, "Close door")

    # ─────────────────────────────────────────────────────────────────────────
    # 3.3 Standby / Poke
    # ─────────────────────────────────────────────────────────────────────────
    @_with_session_retry
    def wakeup_from_standby(self) -> bool:
        """
        Try to wake the balance from standby using IBasicService.WakeupFromStandby.

        Returns
        -------
        bool
            True if `IsStandbyActive` is False (standby no longer active).
        """
        resp = _soap(self, self._svc_basic.WakeupFromStandby, SessionId=self.session_id)
        return (resp or {}).get("IsStandbyActive") is False

    def _poke_display(self):
        """
        Small "nudge" on the DraftShieldsService.GetPosition.

        This often helps when the SOAP UI or internal stack is half-asleep.
        Any error is silently ignored.
        """
        try:
            _ = _soap(
                self,
                self._svc_draft.GetPosition,
                SessionId=self.session_id,
                DraftShieldIds={"DraftShieldIdentifier": list(self.door_ids or [])},
            )
        except Exception:
            # harmless nudge: ignore all errors
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # 3.4 Weighing: Zero / Tare / GetWeight(s)
    # ─────────────────────────────────────────────────────────────────────────
    @_with_session_retry
    def zero(self) -> str:
        """
        Issue a Zero command on the current weighing task, immediate mode.
        """
        _ = _soap(self, self._svc_weigh.Zero, SessionId=self.session_id, ZeroImmediately=True)
        return "OK"

    @_with_session_retry
    def tare(self) -> str:
        """
        Issue a Tare command on the current weighing task, immediate mode.
        """
        _ = _soap(self, self._svc_weigh.Tare, SessionId=self.session_id, TareImmediately=True)
        return "OK"

    @_with_session_retry
    def get_weights(self, capture_mode: str = "Stable", timeout_s: int = 5) -> dict:
        """
        Get current net and gross weights in grams.

        Parameters
        ----------
        capture_mode : str, default "Stable"
            WeighingCaptureMode requested from the WebService.
        timeout_s : int, default 5
            Timeout (seconds) for the WebService call.

        Returns
        -------
        dict
            Dictionary with keys:
            - 'net_g'   : float or None
            - 'gross_g' : float or None

        The function is robust to different shapes (single sample vs list) and
        will try a fallback "Immediate" call if needed.
        """
        def _call(mode: str):
            return _soap(
                self,
                self._svc_weigh.GetWeight,
                SessionId=self.session_id,
                WeighingCaptureMode=mode,
                TimeoutInSeconds=int(timeout_s),
            )

        def _extract_ws(resp):
            # 1) best effort direct access
            ws = _dig(resp, "WeightSample")
            if ws is not None:
                return ws
            # 2) inner container
            return _dig(resp, "WeighingInformation", "WeightSamples", "WeightSample")

        resp = _call(capture_mode) or {}
        ws = _extract_ws(resp)

        if ws is None:
            # fallback "Immediate"
            resp = _call("Immediate") or {}
            ws = _extract_ws(resp)
            if ws is None:
                # if Outcome explicitly indicates an error → raise,
                # otherwise return None/None
                outc = _dig(resp, "Outcome")
                if outc and str(outc) != "Success":
                    raise RuntimeError(f"GetWeight: Outcome={outc} CommandId={_dig(resp,'CommandId')}")
                return {"net_g": None, "gross_g": None}

        # if we got a list of samples → pick the last one
        if isinstance(ws, list):
            ws = ws[-1]

        # Net/Gross nodes tolerant to dict/object layouts
        net_node = _dig(ws, "NetWeight")
        gro_node = _dig(ws, "GrossWeight")
        net_v, net_u = _read_vu(net_node)
        gro_v, gro_u = _read_vu(gro_node)

        return {"net_g": _to_g(net_v, net_u), "gross_g": _to_g(gro_v, gro_u)}

    def get_weight(self) -> float:
        """
        Convenience:

        - Prefer net weight in grams
        - Fallback to gross weight
        - If nothing is available, return 0.0 so that the UI logic does not crash.
        """
        w = self.get_weights()
        if w["net_g"] is not None:
            return w["net_g"]
        if w["gross_g"] is not None:
            return w["gross_g"]
        return 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # 3.5 Pan sensing: empty / presence
    # ─────────────────────────────────────────────────────────────────────────
    def _sample_gross(self, n=10, sleep_s=0.05) -> List[float]:
        """
        Collect a small series of gross weights in grams using 'Immediate' mode.
        """
        vals = []
        for _ in range(max(3, int(n))):
            w = self.get_weights(capture_mode="Immediate", timeout_s=1)
            if w["gross_g"] is not None:
                vals.append(w["gross_g"])
            time.sleep(sleep_s)
        return vals

    def is_pan_empty(self, threshold_mg: float = 9.0, samples: int = 10, sleep_s: float = 0.05):
        """
        Heuristic test to detect whether the pan is empty.

        Parameters
        ----------
        threshold_mg : float, default 9.0
            Baseline threshold in milligrams.
        samples : int, default 10
            Number of gross-weight samples to gather.
        sleep_s : float, default 0.05
            Delay between samples.

        Returns
        -------
        (bool, dict)
            - bool: True if |mean| < threshold (adaptively >= 5*std)
            - dict: statistics {mean_gross_g, std_gross_g, threshold_g, n}
        """
        vals = self._sample_gross(samples, sleep_s)
        if not vals:
            thr = threshold_mg / 1000.0
            return (False, {"mean_gross_g": 0.0, "std_gross_g": 0.0, "threshold_g": thr, "n": 0})
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1)
        std = var ** 0.5
        thr = max(threshold_mg / 1000.0, 5.0 * std)
        return (
            abs(mean) < thr,
            {"mean_gross_g": mean, "std_gross_g": std, "threshold_g": thr, "n": len(vals)},
        )

    def is_pan_present(self, min_present_mg: float = 1000.0, samples: int = 10, sleep_s: float = 0.05):
        """
        Heuristic test to detect whether there is something clearly present on the pan.

        Parameters
        ----------
        min_present_mg : float, default 1000.0
            Minimum presence threshold in milligrams.
        samples : int, default 10
            Number of gross-weight samples to gather.
        sleep_s : float, default 0.05
            Delay between samples.

        Returns
        -------
        (bool, dict)
            - bool: True if mean >= threshold
            - dict: statistics {mean_gross_g, std_gross_g, threshold_g, n}
        """
        vals = self._sample_gross(samples, sleep_s)
        if not vals:
            thr = float(min_present_mg) / 1000.0
            return (False, {"mean_gross_g": 0.0, "std_gross_g": 0.0, "threshold_g": thr, "n": 0})
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1)
        std = var ** 0.5
        thr = float(min_present_mg) / 1000.0
        return (
            mean >= thr,
            {"mean_gross_g": mean, "std_gross_g": std, "threshold_g": thr, "n": len(vals)},
        )

    def get_door_positions(self) -> Dict[str, int]:
        """
        Public helper for WM: ensure a valid session then return door positions.
        """
        self._ensure_session()
        return self._draft_positions()

    # ─────────────────────────────────────────────────────────────────────────
    # 3.6 Methods & Tolerances (WeighingTask) — compact helpers
    # ─────────────────────────────────────────────────────────────────────────
    def _start_task(self, method_name: str):
        """Start a weighing task for the given method name."""
        _ = _soap(self, self._svc_wtask.StartTask, SessionId=self.session_id, MethodName=method_name)
        self._method_name = method_name
        self._task_ready = True

    def _ensure_task_started(self):
        """
        Ensure a weighing task is active.

        Tries to read target/tolerances; if that fails, tries to start
        the configured method. Some firmwares already have an active task,
        which is tolerated.
        """
        if self._task_ready:
            return
        try:
            _ = _soap(self, self._svc_wtask.GetTargetValueAndTolerances, SessionId=self.session_id)
            self._task_ready = True
            return
        except Exception:
            pass
        try:
            self._start_task(self._method_name)
        except Exception:
            # some firmwares already have an active task; ignore errors here
            pass

    def set_method(self, method_name: str) -> str:
        """
        Explicitly start a weighing task for a given method name.
        """
        self._task_ready = False
        self._start_task(method_name)
        return "OK"

    def _get_target_and_tols(self):
        """
        Read current target weight and tolerances from the WeighingTask service.

        Returns
        -------
        (t_v, t_u, up_v, lo_v, tol_u)
          t_v  : target value (float or None)
          t_u  : target unit (str)
          up_v : upper tolerance value (float)
          lo_v : lower tolerance value (float)
          tol_u: tolerance unit (str)
        """
        try:
            r = _soap(self, self._svc_wtask.GetTargetValueAndTolerances, SessionId=self.session_id) or {}
        except Exception:
            return None, "Gram", 0.0, 0.0, "Percent"

        def _read(node):
            v, u = _read_vu(node)
            return _to_float(v), (u or "Gram")

        t_v, t_u = _read(r.get("TargetWeight"))
        up_v, up_u = _read(r.get("UpperTolerance"))
        lo_v, lo_u = _read(r.get("LowerTolerance"))
        tol_u = up_u or lo_u or "Percent"
        return t_v, (t_u or "Gram"), (up_v or 0.0), (lo_v or 0.0), tol_u

    @_with_session_retry
    def set_target_weight(
        self,
        value: float,
        unit: str = "g",
        tol_plus: float | None = None,
        tol_minus: float | None = None,
        tol_unit: str | None = None,
    ) -> str:
        """
        Set the target weight and tolerances for the current weighing task.

        Any tolerance parameter left to None will keep the current value
        read from the WebService.
        """
        self._ensure_task_started()
        _, _, cur_up, cur_lo, cur_u = self._get_target_and_tols()
        req = {
            "SessionId": self.session_id,
            "TargetWeight": {"Value": float(value), "Unit": _ws_unit(unit)},
            "LowerTolerance": {
                "Value": float(cur_lo if tol_minus is None else tol_minus),
                "Unit": _ws_unit(tol_unit or cur_u),
            },
            "UpperTolerance": {
                "Value": float(cur_up if tol_plus is None else tol_plus),
                "Unit": _ws_unit(tol_unit or cur_u),
            },
        }
        _ = _soap(self, self._svc_wtask.SetTargetValueAndTolerances, **req)
        return "OK"

    def set_tolerance_upper(self, value: float, unit: str = "%") -> str:
        """
        Convenience: set upper tolerance, keeping target and lower tolerance.
        """
        t_v, t_u, _, cur_lo, cur_u = self._get_target_and_tols()
        if t_v is None:
            t_v, t_u = 0.0, "Gram"
        return self.set_target_weight(t_v, t_u, tol_plus=value, tol_minus=cur_lo, tol_unit=(unit or cur_u))

    def set_tolerance_lower(self, value: float, unit: str = "%") -> str:
        """
        Convenience: set lower tolerance, keeping target and upper tolerance.
        """
        t_v, t_u, cur_up, _, cur_u = self._get_target_and_tols()
        if t_v is None:
            t_v, t_u = 0.0, "Gram"
        return self.set_target_weight(t_v, t_u, tol_plus=cur_up, tol_minus=value, tol_unit=(unit or cur_u))

    # ─────────────────────────────────────────────────────────────────────────
    # 3.7 Dosing (simple job) & Dosing Head
    # ─────────────────────────────────────────────────────────────────────────
    @_with_session_retry
    def start_dosing_job(
        self,
        vial_name: str,
        substance_name: str,
        target_value: float,
        target_unit: str = "mg",
        lower_tol_value: float | None = None,
        upper_tol_value: float | None = None,
        tol_unit: str | None = None,
    ) -> dict:
        """
        Start a simple DosingAutomation job list with a single job.

        Ensures the 'Dosing' method is active before sending the job list.
        """
        # Make sure we are in the correct method
        if not self._method_name or self._method_name.strip().lower() != "dosing":
            try:
                self._start_task("Dosing")
            except Exception as e:
                raise RuntimeError(
                    f"Impossible de démarrer la méthode 'Dosing' avant le job: {e}"
                )

        tu = _ws_unit(target_unit)
        tol_u = _ws_unit(tol_unit or target_unit)
        lo = 0.0 if lower_tol_value is None else float(lower_tol_value)
        up = 0.0 if upper_tol_value is None else float(upper_tol_value)

        job = {
            "VialName": vial_name,
            "SubstanceName": substance_name,
            "TargetWeight": {"Value": float(target_value), "Unit": tu},
            "LowerTolerance": {"Value": lo, "Unit": tol_u},
            "UpperTolerance": {"Value": up, "Unit": tol_u},
        }
        req = {"SessionId": self.session_id, "DosingJobList": {"DosingJob": [job]}}

        resp = _soap(self, self._svc_dosing.StartExecuteDosingJobListAsync, **req) or {}
        self._last_async_cmd_id = resp.get("CommandId")
        return {
            "Outcome": str(resp.get("Outcome")) if resp.get("Outcome") is not None else None,
            "CommandId": resp.get("CommandId"),
            "ErrorMessage": resp.get("ErrorMessage"),
            "StartDosingJobListError": str(resp.get("StartDosingJobListError"))
            if resp.get("StartDosingJobListError") is not None
            else None,
            "JobErrors": resp.get("JobErrors"),
        }

    @_with_session_retry
    def cancel_dosing_job_list(self) -> dict:
        """
        Cancel the current dosing job list.

        Uses IDosingAutomationService.CancelCurrentDosingJobListAsync.
        """
        resp = (
            _soap(self, self._svc_dosing.CancelCurrentDosingJobListAsync, SessionId=self.session_id) or {}
        )
        # After success, the balance will send a DosingAutomationFinishedAsyncNotification
        return {
            "Outcome": str(resp.get("Outcome")) if resp.get("Outcome") is not None else None,
            "ErrorMessage": resp.get("ErrorMessage"),
            "CommandId": resp.get("CommandId"),
        }

    @_with_session_retry
    def cancel_current_task(self) -> dict:
        """
        Cancel the current weighing task.

        Uses IWeighingTaskService.CancelCurrentTask.
        """
        resp = _soap(self, self._svc_wtask.CancelCurrentTask, SessionId=self.session_id) or {}
        return {
            "Outcome": str(resp.get("Outcome")) if resp.get("Outcome") is not None else None,
            "ErrorMessage": resp.get("ErrorMessage"),
        }

    @_with_session_retry
    def cancel_command(self, cmd_id: Optional[int] = None) -> dict:
        """
        Cancel an asynchronous command by CommandId using ISessionService.Cancel.

        Some firmwares do not support CancelType and will require the fallback
        call without CancelType.
        """
        cmd = int(cmd_id if cmd_id is not None else (self._last_async_cmd_id or -1))
        if cmd < 0:
            return {"Outcome": None, "ErrorMessage": "No CommandId to cancel"}
        # Documentation mentions CancelType; a typical value is 'CommandId'
        try:
            resp = (
                _soap(
                    self,
                    self._svc_session.Cancel,
                    SessionId=self.session_id,
                    CancelType="CommandId",
                    CommandId=cmd,
                )
                or {}
            )
        except Exception:
            # some firmwares do not implement CancelType → fallback without it
            resp = (
                _soap(self, self._svc_session.Cancel, SessionId=self.session_id, CommandId=cmd)
                or {}
            )
        return {
            "Outcome": str(resp.get("Outcome")) if resp.get("Outcome") is not None else None,
            "ErrorMessage": resp.get("ErrorMessage"),
        }

    @_with_session_retry
    def read_dosing_head_name(self) -> str:
        """
        Read the current dosing head information and return the SubstanceName.
        """
        resp = _soap(self, self._svc_dosing.ReadDosingHead, SessionId=self.session_id) or {}
        substance = ((resp.get("DosingHeadInfo") or {}).get("SubstanceName"))
        return str(substance or "")

    @_with_session_retry
    def write_dosing_head_name(self, name: str) -> str:
        """
        Write a new substance name into the dosing head via WriteDosingHead.

        Preserves HeadType and HeadId read from ReadDosingHead.
        """
        cur = _soap(self, self._svc_dosing.ReadDosingHead, SessionId=self.session_id) or {}
        head_type = cur.get("HeadType")
        head_id = cur.get("HeadId")
        if not head_type:
            raise RuntimeError("WriteDosingHead: HeadType introuvable (ReadDosingHead)")

        req = {
            "SessionId": self.session_id,
            "HeadType": head_type,
            "DosingHeadInfo": {"SubstanceName": str(name)},
        }
        if head_id:
            req["HeadId"] = head_id

        resp = _soap(self, self._svc_dosing.WriteDosingHead, **req) or {}
        outcome = resp.get("Outcome")
        if outcome is not None and str(outcome) != "Success":
            raise RuntimeError(f"WriteDosingHead Outcome={outcome}")
        return "OK"

    @_with_session_retry
    def confirm_dosing_action(self, action: str, action_item: str | None = None) -> dict:
        """
        Confirm a requested dosing job action (e.g. 'Continue') back to the WebService.
        """
        req = {
            "SessionId": self.session_id,
            "ExecutedDosingJobAction": str(action),
            "ActionItem": action_item or "",
        }
        resp = _soap(self, self._svc_dosing.ConfirmDosingJobAction, **req) or {}
        return {
            "Outcome": str(resp.get("Outcome")) if resp.get("Outcome") is not None else None,
            "ErrorMessage": resp.get("ErrorMessage"),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 3.8 Notifications — simple "option A" with serialized dicts
    # ─────────────────────────────────────────────────────────────────────────
    def _notif_list(self, resp_dict: dict) -> List[dict]:
        """
        Extract a flat list of notifications from the raw GetNotifications reply.
        """
        r = resp_dict or {}
        c = r.get("Notifications") or {}
        inner = c.get("_value_1") or c.get("Notification") or c.get("Notifications")
        if inner is None:
            return []
        return inner if isinstance(inner, list) else [inner]

    def auto_confirm_dosing_notifications(
        self,
        log_cb: Callable[[str], None] | None = None,
        long_poll_s: int = 10,
        verbose: bool = False,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Poll notifications from the NotificationService and:

        - Auto-confirm DosingAutomationActionAsyncNotification entries.
        - Log DosingAutomationJobFinishedAsyncNotification details.
        - Return when DosingAutomationFinishedAsyncNotification is received
          or when stop_event is set.

        All messages are passed to `log_cb` if provided.
        """
        def log(msg: str, force: bool = False):
            if (verbose or force) and log_cb:
                log_cb(msg)

        # NOTE: log messages stay in French on purpose
        log("Démarrage auto_confirm_dosing_notifications()", True)

        while True:
            if stop_event is not None and stop_event.is_set():
                log("Stop demandé → sortie du polling de notifications.", True)
                return
            try:
                resp = _soap(
                    self,
                    self._svc_notify.GetNotifications,
                    SessionId=self.session_id,
                    LongPollingTimeout=int(long_poll_s),
                ) or {}
            except Exception as e:
                log(f"ERREUR GetNotifications: {e}", True)
                if "Session" in str(e):
                    log("→ tentative de réouverture de session", True)
                    self._open_session()
                    continue
                return

            for n in self._notif_list(resp):
                if not isinstance(n, dict):
                    continue

                # 1) Action to be confirmed
                if "DosingAutomationActionAsyncNotification" in n:
                    notif = n.get("DosingAutomationActionAsyncNotification") or {}
                    action = (
                        notif.get("DosingJobActionType")
                        or notif.get("RequestedDosingJobAction")
                        or notif.get("ExecutedDosingJobAction")
                    )
                    item = notif.get("ActionItem")
                    log(f"Dosing action: {action} / {item}", True)
                    if action:
                        self.confirm_dosing_action(str(action), item)
                    continue

                # 2) Single job finished
                if "DosingAutomationJobFinishedAsyncNotification" in n:
                    jn = n.get("DosingAutomationJobFinishedAsyncNotification") or {}
                    dres = jn.get("DosingResult", {})
                    job = dres.get("DosingJob", {})
                    ws = dres.get("WeightSample", {})

                    t_v, t_u = _read_vu(job.get("TargetWeight"))
                    n_v, n_u = _read_vu(ws.get("NetWeight"))
                    lo_v, lo_u = _read_vu(job.get("LowerTolerance"))
                    up_v, up_u = _read_vu(job.get("UpperTolerance"))

                    log(
                        f"Job fini: Outcome={jn.get('Outcome')} "
                        f"Target={t_v} {t_u} Net={n_v} {n_u} "
                        f"Tol=-{lo_v} {lo_u}/+{up_v} {up_u}",
                        True,
                    )
                    continue

                # 3) End of job list
                if "DosingAutomationFinishedAsyncNotification" in n:
                    log("Fin DosingAutomation", True)
                    return
            # otherwise loop again


# ─────────────────────────────────────────────────────────────────────────────
# [4] WM facade — public API used by WinBalance
# ─────────────────────────────────────────────────────────────────────────────
class WM:
    """
    Thin facade over _WMWebService.

    This class exposes a stable, high-level API for the GUI (WinBalance),
    while all low-level SOAP details live inside _WMWebService.
    """

    def __init__(self, **override):
        cfg = dict(SCALE_CONFIG)
        cfg.update(override)
        self._impl = _WMWebService(cfg)

    # Session / state
    def connect(self):              return self._impl.connect()
    def close(self):                return self._impl.close()
    def is_connected(self):         return self._impl.is_connected()

    # Doors
    def open_door(self):            return self._impl.open_door()
    def close_door(self):           return self._impl.close_door()
    def wakeup_from_standby(self):  return self._impl.wakeup_from_standby()
    def get_door_positions(self) -> Dict[str, int]: return self._impl.get_door_positions()

    # Weighing
    def zero(self):                 return self._impl.zero()
    def tare(self):                 return self._impl.tare()
    def get_weight(self):           return self._impl.get_weight()
    def get_weights(self, *a, **k): return self._impl.get_weights(*a, **k)

    # Pan sensing
    def is_pan_empty(self, *a, **k):   return self._impl.is_pan_empty(*a, **k)
    def is_pan_present(self, *a, **k): return self._impl.is_pan_present(*a, **k)

    # Methods & tolerances
    def set_method(self, name: str):        return self._impl.set_method(name)
    def set_target_weight(self, *a, **k):   return self._impl.set_target_weight(*a, **k)
    def set_tolerance_upper(self, *a, **k): return self._impl.set_tolerance_upper(*a, **k)
    def set_tolerance_lower(self, *a, **k): return self._impl.set_tolerance_lower(*a, **k)

    # Dosing
    def start_dosing_job(self, *a, **k):      return self._impl.start_dosing_job(*a, **k)
    def confirm_dosing_action(self, *a, **k): return self._impl.confirm_dosing_action(*a, **k)
    def auto_confirm_dosing_notifications(self, *a, **k): return self._impl.auto_confirm_dosing_notifications(*a, **k)
    def cancel_dosing_job_list(self, *a, **k): return self._impl.cancel_dosing_job_list(*a, **k)
    def cancel_current_task(self, *a, **k):    return self._impl.cancel_current_task(*a, **k)
    def cancel_command(self, *a, **k):         return self._impl.cancel_command(*a, **k)

    # Dosing head
    def get_dosing_head_name(self) -> str:            return self._impl.read_dosing_head_name()
    def set_dosing_head_name(self, name: str) -> str: return self._impl.write_dosing_head_name(name)
