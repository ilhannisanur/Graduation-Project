"""Fixed choices a listener can pick in their profile.

Values are stored in the database; genres are also sent in `ListenerContext`. Labels are only
for display.
Genre values follow Jamendo's genre tags so the catalog can be matched against them later.
"""

GENRES: dict[str, str] = {
    "pop": "Pop",
    "rock": "Rock",
    "electronic": "Electronic",
    "hiphop": "Hip-hop",
    "jazz": "Jazz",
    "classical": "Classical",
    "ambient": "Ambient",
    "folk": "Folk",
    "metal": "Metal",
    "blues": "Blues",
    "reggae": "Reggae",
    "rnb": "R&B",
    "latin": "Latin",
    "world": "World",
    "soundtrack": "Soundtrack",
}

# ISO 639-1 codes: the languages a listener likes songs in.
LANGUAGES: dict[str, str] = {
    "en": "English",
    "tr": "Turkish",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
}
