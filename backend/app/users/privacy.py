"""The privacy notice shown to listeners and the consents they can give.

Change NOTICE_VERSION whenever the text changes in meaning: every consent row records the
version it was given under, so we can show what the listener agreed to.
"""

NOTICE_VERSION = "2026-10-27"

PREFERENCE_LEARNING = "preference_learning"

# kind -> what the listener is agreeing to (shown next to the switch)
CONSENT_KINDS: dict[str, str] = {
    PREFERENCE_LEARNING: (
        "Learn from what I listen to: songs I play, like, skip or request again shape "
        "what the radio picks for me."
    ),
}

# (title, text) pairs. Keep this in sync with what the code really does.
NOTICE: list[tuple[str, str]] = [
    (
        "What we store",
        "Your username and a scrambled (hashed) form of your password, which nobody can turn "
        "back into the password. Your profile: genres, song languages, news topics, favourite "
        "artists and the city for weather. When you signed in and until when that sign-in "
        "is valid. Your choices on this page and when you made them. We do not ask for your "
        "e-mail, phone number or real name.",
    ),
    (
        "Why",
        "To run your personal radio: to choose music, news and weather that suit you. "
        "Nothing is sold or shared for advertising.",
    ),
    (
        "What the AI presenter sees",
        "The presenter's words are written by an external AI service. It only receives your "
        "genres, news topics, city and the local time. It never receives your username, "
        "password or favourite artists.",
    ),
    (
        "Learning from your listening (optional)",
        "Off unless you turn it on. When on, the songs you play, like, skip or request again "
        "help choose your music. You can turn it off at any time; from then on your "
        "listening is no longer used for this.",
    ),
    (
        "Your rights",
        "You can see and download all your data, change your profile, turn learning off and "
        "delete your account. Deleting your account removes all of your data at once and "
        "ends your sessions.",
    ),
    (
        "Who we are",
        "This radio is a university graduation project, not a commercial service.",
    ),
]
