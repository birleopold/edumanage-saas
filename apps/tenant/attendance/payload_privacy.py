"""Privacy boundary for raw attendance-device payloads.

EduManage needs enough raw metadata to audit a punch, diagnose vendor mappings and
replay normalization decisions. It does not need fingerprint templates, face
images or other biometric enrollment material in the attendance event ledger.
"""

from collections.abc import Mapping


REDACTED = "[REDACTED_BY_EDUMANAGE]"
MAX_TEXT_VALUE = 16_384
MAX_LIST_ITEMS = 1_000
MAX_DEPTH = 8

SENSITIVE_EXACT_KEYS = {
    "biometric",
    "biometric_data",
    "biometricdata",
    "face_image",
    "faceimage",
    "face_photo",
    "facephoto",
    "face_template",
    "facetemplate",
    "finger_image",
    "fingerimage",
    "fingerprint",
    "fingerprint_data",
    "fingerprintdata",
    "fingerprint_template",
    "fingerprinttemplate",
    "image",
    "photo",
    "picture",
    "portrait",
    "template",
    "template_data",
    "templatedata",
    "palm_template",
    "palmtemplate",
    "iris_template",
    "iristemplate",
}


def _normalized_key(key) -> str:
    return str(key or "").strip().lower().replace("-", "_").replace(" ", "_")


def _is_sensitive_key(key) -> bool:
    normalized = _normalized_key(key)
    if normalized in SENSITIVE_EXACT_KEYS:
        return True
    return (
        ("finger" in normalized or "face" in normalized or "palm" in normalized or "iris" in normalized)
        and ("template" in normalized or "image" in normalized or "photo" in normalized or "picture" in normalized or "data" in normalized)
    )


def scrub_attendance_payload(value, *, depth=0):
    if depth >= MAX_DEPTH:
        return "[TRUNCATED_NESTING]"
    if isinstance(value, Mapping):
        output = {}
        for key, item in value.items():
            text_key = str(key)
            output[text_key] = REDACTED if _is_sensitive_key(text_key) else scrub_attendance_payload(item, depth=depth + 1)
        return output
    if isinstance(value, (list, tuple)):
        cleaned = [scrub_attendance_payload(item, depth=depth + 1) for item in value[:MAX_LIST_ITEMS]]
        if len(value) > MAX_LIST_ITEMS:
            cleaned.append(f"[TRUNCATED_{len(value) - MAX_LIST_ITEMS}_ITEMS]")
        return cleaned
    if isinstance(value, bytes):
        return f"[BINARY_REDACTED_{len(value)}_BYTES]"
    if isinstance(value, str) and len(value) > MAX_TEXT_VALUE:
        return value[:MAX_TEXT_VALUE] + f"...[TRUNCATED_{len(value) - MAX_TEXT_VALUE}_CHARS]"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
