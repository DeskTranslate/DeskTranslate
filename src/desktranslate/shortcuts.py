"""Pure validation of configurable global shortcuts."""


def parse_hotkey(value: str) -> tuple[int, int]:
    parts = value.upper().split("+")
    modifiers = {"CTRL": 2, "ALT": 1, "SHIFT": 4, "WIN": 8}
    if len(parts) < 2 or len(set(parts)) != len(parts):
        raise ValueError("Use modifiers and a letter, digit or F1–F12, such as Ctrl+Alt+T.")
    mask = 0x4000  # MOD_NOREPEAT
    for part in parts[:-1]:
        if part not in modifiers:
            raise ValueError("Use Ctrl, Alt, Shift or Win as modifiers.")
        mask |= modifiers[part]
    key = parts[-1]
    if len(key) == 1 and key.isascii() and key.isalnum():
        return mask, ord(key)
    if key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
        return mask, 111 + int(key[1:])
    raise ValueError("Use a letter, digit or F1–F12.")


def validate_hotkeys(values: dict[str, str]) -> None:
    parsed = [parse_hotkey(value) for value in values.values()]
    if len(parsed) != len(set(parsed)):
        raise ValueError("Two actions use the same shortcut. Choose different keys.")
