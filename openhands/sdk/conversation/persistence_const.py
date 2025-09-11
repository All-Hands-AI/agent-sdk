import re


BASE_STATE = "base_state.json"
EVENTS_DIR = "events"
EVENT_NAME_RE = re.compile(r"^event-(?P<idx>\d{5})\.json$")
EVENT_ID_PATTERN = "{idx:05d}"
EVENT_FILE_PATTERN = "event-" + EVENT_ID_PATTERN + ".json"
