"""English UI texts. Same names, signatures and `{placeholders}` as strings.py, which overrides its Spanish values with
these when the active language is «en» (see core/language.py). Keep both files in sync: tests/unit/test_language.py checks it."""
from ..core.platform_info import IS_MAC as _IS_MAC, IS_WINDOWS as _IS_WINDOWS

# How the API Key is protected depending on the system.
_KEY_STORE = "with Windows" if _IS_WINDOWS else "in the macOS Keychain" if _IS_MAC else "in the system keychain"
_ABOUT_PROTECTION = (
    "API Keys are encrypted with Windows (DPAPI) for your Windows user. This protects against other users of the "
    "computer and against copying the files to another machine; it does not protect against malicious software "
    "running as your own user. If Windows recreates your profile, the keys are lost and must be entered again."
    if _IS_WINDOWS else
    "API Keys are stored in the system keychain (" + ("macOS Keychain" if _IS_MAC else
                                                       "Secret Service: GNOME Keyring or KWallet") +
    "), tied to your user. This protects against other users of the computer and against copying the files to another "
    "machine; it does not protect against malicious software running as your own user. If the keychain is reset or "
    "erased, the keys must be entered again.")
APP_NAME = "Tally Monitor"
TEST_MODE_SUFFIX = " — TEST MODE"
TEST_MODE_BADGE = "Test mode: a session report is saved when you close the app."
TEST_REPORT_SAVED = "Session report saved to:\n{path}"

NAV = [("inicio", "Home"), ("encuestas", "Surveys"), ("cuentas", "Accounts"), ("configuracion", "Settings")]
TABS = [("resumen", "Summary"), ("respuestas", "Responses"), ("exportar", "Export")]

COMING: dict = {}

# accounts
ACCOUNTS_TITLE = "Accounts"
ADD_ACCOUNT = "+ Add account"
ADD_FIRST = "Add your first account"
NO_ACCOUNTS_TITLE = "No accounts yet"
NO_ACCOUNTS_TEXT = "Add a Tally API Key to get started. It is stored encrypted on this computer and is never shown again."
KEY_SAVED = "Key saved and encrypted"
BTN_VALIDATE, BTN_RENAME, BTN_REPLACE, BTN_DELETE = "Validate", "Rename", "Replace key", "Delete"
ADD_TITLE = "Add account"
ADD_HELP = ("Paste your Tally API Key (it starts with “tly-”). It is checked with Tally and only then saved, "
            f"encrypted {_KEY_STORE}. Data is only read: nothing is ever modified in Tally.")
FIELD_NAME, FIELD_KEY = "Account name", "API Key"
BTN_CLOSE = "Close"
BTN_SAVE_VALIDATE, BTN_CANCEL, BTN_REPLACE_OK = "Validate and save", "Cancel", "Validate and replace"
REPLACE_TITLE = "Replace key"
REPLACE_HELP = ("The new key is validated. If it fails, or belongs to another Tally user, "
                "the current key is kept.")
VALIDATING = "Validating with Tally…"
RENAME_TITLE, RENAME_LABEL = "Rename account", "New name:"
DELETE_TITLE = "Delete account"
DELETE_TEXT = ("Delete the account “{name}”?\n\nIts encrypted key and the saved data of this account are removed "
               "from this computer. Nothing is touched in Tally.")
DELETE_CONFIRM = "Delete"
IDENTITY_NOT_VERIFIED = ("The key was replaced, but it could not be checked that it belongs to the same Tally user "
                         "(the identifier of one of the two is missing).")
KEY_REPLACED = "Key replaced and validated."

# statuses
STATUS_LABELS = {"active": "Active", "key_rejected": "Key rejected", "check_failed": "Could not verify",
                 "no_credential": "No saved key", "unverified": "Not verified"}
CHECK_DETAILS = {"network": "No connection to Tally", "rate_limit": "Tally limited the requests",
                 "server": "The Tally service did not respond", "unexpected": "Unexpected response from Tally",
                 "auth": "Tally rejected the key"}
STATUS_HELP = {"key_rejected": "Replace the key.", "no_credential": "Replace the key: it is missing on this computer.",
               "check_failed": "The key was not marked as invalid. Try validating again."}

# home
HOME_TITLE = "Home"
TILE_ACCOUNTS, TILE_ACTIVE, TILE_ATTENTION = "Accounts", "Active", "Need attention"
ATTENTION_BANNER = "Some accounts need attention. Check them in “Accounts”."
OPEN_ACCOUNTS = "Go to Accounts"

# settings
SETTINGS_TITLE = "Settings"
SEC_DATA, SEC_LOGS, SEC_ABOUT = "Data and backups", "Log", "About"
DATA_FOLDER, OPEN_FOLDER = "Data folder:", "Open folder"
BACKUP_NOW, BACKUP_RESTORE, BACKUP_DELETE = "Create backup now", "Restore…", "Delete backup"
AUTO_BACKUP = "Daily automatic backup on startup"
BACKUP_HEADERS = ["Date", "Reason", "Schema", "Size"]
BACKUP_NOTE = "Backups do not include API Keys: after restoring on another computer you have to enter them again."
BACKUP_CREATED = "Backup created."
BACKUP_DELETED = "Backup deleted."
RESTORE_TITLE = "Restore backup"
RESTORE_TEXT = ("Restore the backup from {date}?\n\nThe current database is replaced (a backup of the current state is "
                "saved first). Saved keys are not touched; accounts without a key "
                "will show as “No saved key”.")
RESTORE_OK = "Backup restored."
RESTORE_RESTART = "Backup restored. Close and reopen the application."
DELETE_BACKUP_TEXT = "Delete the backup from {date}? This cannot be undone."
REASONS = {"auto": "Automatic", "manual": "Manual", "pre_migracion": "Before migration",
           "pre_restauracion": "Before restore", "pre_reconciliacion": "Before reconciliation"}
LOG_LEVEL, LOGS_FOLDER = "Detail level:", "Open logs folder"
ALREADY_RUNNING = "Tally Monitor is already open. Look for it in the taskbar."
COPY_DIAG, DIAG_COPIED = "Copy diagnostic report", "Report copied. Paste it wherever you need: it does not include API Keys, responses or names."
LOG_NOTE = "Logs never include API Keys."
ABOUT_TEXT = "Tally Monitor {version}\nRead-only: it does not modify anything in Tally.\n\n" + _ABOUT_PROTECTION
LICENSES = "Third-party licenses"
LICENSES_TEXT = ("PySide6 / Qt for Python — LGPL-3.0 (used under the LGPL, dynamically linked).\n"
                 "Python and its standard library — Python Software Foundation License.\n\n"
                 "Full details in THIRD_PARTY_LICENSES.md.")
DEGRADED = ("The database is damaged. Restore a backup to continue; "
            "the other sections are disabled.")

GENERIC_ERROR = "An unexpected error occurred. Try again."
BUSY = "Working…"


# surveys
SURVEYS_TITLE = "Your surveys"
SURVEYS_ACCOUNT = "Account:"
SURVEYS_SEARCH = "Search by name…"
SURVEYS_FILTERS = [("all", "All"), ("fav", "Favorites"), ("recent", "Recent")]
SURVEYS_REFRESH = "Refresh list"
SURVEYS_NO_ACCOUNTS_TITLE = "Add an account first"
SURVEYS_NO_ACCOUNTS_TEXT = "Surveys are read with the API Key of a Tally account."
SURVEYS_NO_ACCOUNTS_ACTION = "Go to Accounts"
SURVEYS_EMPTY_TITLE = "No saved surveys yet"
SURVEYS_EMPTY_TEXT = ("Tap “Refresh list” to fetch this account's surveys. "
                      "They are saved on this computer and can be viewed offline.")
SURVEYS_EMPTY_FILTER = "No surveys match the filter."
SURVEYS_LISTING = "Updating the survey list…"
SURVEYS_LISTED = "List updated: {n} survey(s)."
OFFLINE_SHOWING_SAVED = "Could not connect. Showing what is already saved."
BTN_OPEN = "Open"
FAV_ON, FAV_OFF = "Favorite", "Mark as favorite"
SURVEY_OPEN, SURVEY_CLOSED = "Open", "Closed"
SURVEY_DRAFT = "Draft"
NEW_IN_TALLY = "There are new responses in Tally"
NEVER_SYNCED = "Not synced"

# detail
BACK_TO_SURVEYS = "All surveys"
BTN_SYNC, BTN_SYNC_FULL, BTN_CANCEL_SYNC = "Refresh", "Full sync…", "Cancel"
SYNC_FULL_TITLE = "Full sync"
SYNC_FULL_TEXT = ("All the responses of this survey are downloaded again to detect edits and responses "
                  "that are no longer in Tally. A backup is created first. The “User” numbers do not change. "
                  "It can take a while if there are many responses.")
SYNC_FULL_CONFIRM = "Sync everything"
SYNCING = "Syncing…"
SYNC_PHASES = {"encuestas": "Downloading surveys", "respuestas": "Downloading responses"}
SYNC_CANCELLED = "Sync cancelled. What was already saved is still available; you can resume whenever you want."
RESPONSES_HEADER = "Responses"
RESPONSES_SEARCH = "Search user (e.g. 012)…"
NO_RESPONSES_TITLE = "No saved responses yet"
NO_RESPONSES_TEXT = "Tap “Sync” to download them from Tally."
NO_RESPONSES_EMPTY_SURVEY = "This survey has no responses in Tally."
SELECT_A_USER = "Choose a user from the list to see their response."
LOAD_MORE = "Load more"
SHOWING_COUNT = "Showing {shown} of {total}"
USER_NOT_FOUND = "There is no user with that number."
PRIVACY_NOTICE = ("Open-ended responses may contain personal data that participants wrote "
                  "voluntarily. Handle them with care and do not share them unnecessarily.")
ANSWER_BLANK = "(no response)"
ANSWER_RAW = "(response format not interpreted)"
ANSWER_OTHER, ANSWER_UNMATCHED = "(other)", "(option that no longer exists in the survey)"
INCOMPLETE_RESPONSE = "Incomplete response"
SUBMITTED_AT = "{when}"

# sync settings
SEC_SYNC = "Sync"
SYNC_MODE_LABEL = "Sync mode:"
SYNC_MODES = [("manual", "Manual (recommended)"), ("auto", "Automatic")]
SYNC_MODE_NOTE = ("Manual: it only syncs when you tap the button. Automatic: opening Surveys refreshes the "
                  "list and opening a survey fetches its new responses. In both modes what is already saved "
                  "is shown first.")


# analysis
ANALYSIS_TITLE = "Analysis"
ANALYSIS_SURVEY = "Survey:"
ANALYSIS_PERIOD = "Period:"
ANALYSIS_FILTERS = [("all", "All time"), ("24h", "Last 24 hours"), ("7d", "Last 7 days"),
                    ("30d", "Last 30 days"), ("custom", "Custom range")]
ANALYSIS_FROM, ANALYSIS_TO = "From:", "To:"
ANALYSIS_INCLUDE_INCOMPLETE = "Include incomplete submissions"
ANALYSIS_NO_SURVEYS_TITLE = "No responses to analyze yet"
ANALYSIS_NO_SURVEYS_TEXT = ("Open a survey in “Surveys” and tap “Sync”. The analysis uses what is already "
                            "saved on this computer; it needs no connection.")
ANALYSIS_GO_SURVEYS = "Go to Surveys"
ANALYSIS_DATA_FROM = "Data from the last sync ({when}). To update it, sync the survey in “Surveys”."
ANALYSIS_EMPTY_PERIOD = "There are no responses in this period."
ANALYSIS_INVALID_RANGE = "The start date is after the end date."
ANALYSIS_TILES = ("Responses", "Complete", "Incomplete", "Average per day")
ANALYSIS_SPAN = "First response: {first} · Last: {last}"
ANALYSIS_TIMELINE = "Responses over time"
ANALYSIS_BUCKETS = {"hour": "by hour", "day": "by day", "month": "by month"}
ANALYSIS_QUESTIONS = "Questions"
ANALYSIS_ANSWERED = "{n} answered"
ANALYSIS_BLANK = "{n} blank"
ANALYSIS_NOT_ASKED = "{n} did not get this question (it was added later)"
ANALYSIS_NOT_INTERPRETED = ("This question type ({type}) has no analysis of its own yet: only the number of "
                            "people who answered is counted.")
ANALYSIS_TEXT_STATS = "Average length: {avg} characters · maximum: {max}"
ANALYSIS_TEXT_HINT = "Text responses are read in “Surveys”, by user."
ANALYSIS_OTHER_ROW = "Other (written text)"
ANALYSIS_ORPHAN_ROW = "Options that no longer exist in the survey"
ANALYSIS_OTHER_VALUES = "“Other” texts: {items}"
ANALYSIS_WARN_NOT_INTERPRETED = "Some questions are of a type that is not analyzed yet; only their number of responses is shown."
ANALYSIS_WARN_LATER_QUESTIONS = "Some questions were added after the first responses; percentages only count those who saw them."
ANALYSIS_DELETED_QUESTION = "(deleted question)"


# exports
EXPORT_TITLE = "Exports"
EXPORT_INTRO = "What is already saved on this computer is exported, with the period and options you choose here."
EXPORT_INCLUDE_TEXT = "Include free-text responses"
EXPORT_MASK = "Hide possible personal data (emails, phone numbers, usernames, long numbers)"
EXPORT_TEXT_WARNING = ("Text responses may contain personal data written voluntarily. Automatic hiding "
                       "helps but guarantees nothing: review the file before sharing it.")
EXPORT_XLSX = "Export to Excel"
EXPORT_PDF = "Export to PDF"
EXPORT_PNG = "Save charts as image (PNG)"
EXPORT_XLSX_HINT = "Excel: summary, statistics, responses over time and one row per user."
EXPORT_PDF_HINT = "PDF: report with charts. Text responses only if you tick the option above."
EXPORT_PNG_HINT = "PNG: one image with the timeline chart and the bars of each choice question."
EXPORT_SAVE_TITLE = "Save as"
EXPORT_FILTERS = {"xlsx": "Excel workbook (*.xlsx)", "pdf": "PDF document (*.pdf)", "png": "PNG image (*.png)"}
EXPORT_BUSY = "Creating the file…"
EXPORT_DONE = "Done. Saved to: {path}"
EXPORT_DONE_EXTRA_TEXT = " Includes text responses{masked}."
EXPORT_MASKED = " (personal data hidden)"
EXPORT_UNMASKED = " (personal data NOT hidden)"
EXPORT_NOTHING = "There are no responses in this period to export."


# exports and analysis
WALL_SUBTITLE = "Tap one to see its responses, the analysis and export it. All in one place."
CARD_RESPONSES = "saved responses"
CARD_RESPONSES_ONE = "saved response"
CARD_NEVER = "not downloaded"
CARD_NEW = "not up to date"
ANALYSIS_CHIPS = [("24h", "24 h"), ("7d", "7 days"), ("30d", "30 days"), ("all", "All"), ("custom", "Pick dates")]
ANALYSIS_WITH_INCOMPLETE = "With incomplete"
ANALYSIS_WITHOUT_INCOMPLETE = "Without incomplete"
EXPORT_SCOPE_SUMMARY = "Survey summary"
EXPORT_SCOPE_INDIVIDUAL = "Individual responses"
EXPORT_WHO_ALL = "Everyone"
EXPORT_WHO_ONE = "One person only"
EXPORT_WHO_PLACEHOLDER = "For example: 7 or User 007"
EXPORT_WHO_NOT_FOUND = "I could not find that person. Try their number (for example 7)."
EXPORT_BIG_XLSX = "Excel\nData to calculate"
EXPORT_BIG_PDF = "PDF\nReport to share"
EXPORT_BIG_PNG = "Image\nThe charts in a PNG"
EXPORT_BIG_PNG_IND = "Image\nNot recommended"
EXPORT_STYLE_LABEL, EXPORT_STYLE_DARK, EXPORT_STYLE_LIGHT = "PDF and image style:", "Dark", "Light"
EXPORT_BIG_PDF_IND = "PDF\nNot recommended, may take long"
EXPORT_BIG_PDF_TITLE = "PDF with many responses"
EXPORT_BIG_PDF_TEXT = ("Not recommended: there are {n} responses and it may take far too long (about {est}), "
                       "and the file will be very large. You can keep using the program meanwhile. "
                       "For something faster, try Excel or narrow the period. Generate it anyway?")
EXPORT_BIG_PDF_CONFIRM = "Generate the PDF anyway"
EXPORT_PNG_IND_TITLE = "Image with individual responses"
EXPORT_PNG_IND_TEXT = ("An image with many responses ends up extremely long and hard to read or share. For individual "
                       "responses, PDF or Excel is better. Do you want to generate the image anyway?")
EXPORT_PNG_IND_CONFIRM = "Generate the image anyway"
EXPORT_PNG_IND_TOO_MANY = ("That is {n} people: too many for a single image (maximum {max}). Choose one person, a "
                           "shorter period, or use PDF or Excel.")
EXPORT_INDIVIDUAL_HINT = "One card per person with what they answered. Questions they did not answer do not appear."
EXPORT_SUMMARY_HINT = "Statistics per question, timeline chart and the general summary."
ANALYSIS_NOTHING_SAVED = "There are no saved responses for this survey yet. Tap “Refresh” to download them."
TEST_MODE_TAG = "Test mode"


# updates and about
SEC_UPDATES = "Updates"
UPDATE_CHECK = "Notify me when there is a new version"
UPDATE_NOTE = ("Off by default. If you turn it on, the program checks the public list of releases on GitHub "
               "(without sending any data about you). It only notifies you: it never downloads or installs anything by itself.")
UPDATE_NOW, UPDATE_OPEN = "Check now", "Open release page"
UPDATE_STATES = {
    "not_configured": "There is no download site configured yet (it is enabled once the project is published).",
    "up_to_date": "You have the latest version.",
    "error": "Could not check right now. Try again later.",
}
UPDATE_AVAILABLE = "A new version is available: {version}."
UPDATE_PILL = "Version {version} available"
FOOTER = "Tally Monitor {platform}: {version}. By: Valentín Mangano"
ABOUT_LICENSE, ABOUT_PRIVACY = "License and third parties", "Privacy"
PRIVACY_TITLE = "Privacy"
PRIVACY_SUMMARY = (
    "Everything stays on your computer: there are no servers of our own and no accounts.\n"
    "Read-only: the program only queries (GET) the Tally API.\n"
    "Your API Key is stored encrypted with " + ("Windows protection" if _IS_WINDOWS else "the system keychain") + ", in a file separate from the databases and backups; "
    "it is never shown, printed, logged or written to any other file.\n"
    "Respondent or session identifiers, and preview or PDF links, are not stored.\n"
    "Open-ended responses are stored locally and may contain personal data that people wrote; "
    "exports can hide them.\n"
    "The update notice is off by default and never downloads or installs anything by itself.")

# appearance
SEC_APPEARANCE = "Appearance"
THEME_DARK, THEME_LIGHT = "Dark", "Light"
THEME_NOTE = "Choose the look of the application. PDFs and images have their own style option when exporting."


# home
HOME_PENDING_TITLE = "Some responses are not up to date"
HOME_PENDING_TEXT = ("Tally reports {n} more response(s) than are saved on this computer, in {s} survey(s).")
HOME_PENDING_TEXT_NOCOUNT = "Some surveys have responses that have not been downloaded yet."
HOME_PENDING_ACTION = "Go to Surveys"
HOME_NO_ACCOUNTS_TITLE = "Let's get started"
HOME_NO_ACCOUNTS_TEXT = "Add the API Key of your Tally account to see how your surveys are doing here."
HOME_NO_SURVEYS_TITLE = "No saved surveys yet"
HOME_NO_SURVEYS_TEXT = "Go to Surveys and tap “Refresh list” to fetch them."
HOME_TILE_SURVEYS, HOME_TILE_RESPONSES, HOME_TILE_OPEN = "surveys", "responses", "open"
HOME_LAST = "Last response received: {when}"
HOME_TOP_TITLE = "How they are doing"
HOME_TOP_META = "{status} · last: {when}"


# ---------- 1.1: goals, notes, tags, archived ----------
BTN_EDIT = "Edit"
EDIT_TITLE = "Edit survey"
EDIT_GOAL_LABEL = "Response goal"
EDIT_GOAL_HELP = "A whole number between 1 and 1,000,000. Leave it empty if you do not want a goal."
EDIT_GOAL_PLACEHOLDER = "For example: 200"
EDIT_NOTE_LABEL = "Note"
EDIT_NOTE_HELP = "Up to 500 characters. It is only yours: it stays on this computer and is not uploaded to Tally."
EDIT_TAGS_LABEL = "Tags"
EDIT_TAGS_HELP = "Up to 8, of up to 24 characters each. Tap a tag to remove it."
EDIT_TAG_PLACEHOLDER = "Type a tag and tap Add"
EDIT_TAG_ADD = "Add"
EDIT_SAVE = "Save"
EDIT_GOAL_NOT_NUMBER = "The goal must be a whole number, without decimals or letters."
EDIT_TAG_REMOVE = "Remove the tag {tag}"
EDIT_SAVED = "Changes saved."
ARCHIVE = "Archive"
UNARCHIVE = "Unarchive"
ARCHIVED_TAG = "Archived"
ARCHIVE_DONE = "Survey archived. It no longer counts in Home or in notifications."
UNARCHIVE_DONE = "Survey unarchived."
SHOW_ARCHIVED = "Show archived"
TAG_ALL = "All"
TAG_FILTER_LABEL = "Tag: {tag}"
SURVEYS_EMPTY_ARCHIVED_HINT = "There are archived surveys: turn on “Show archived” to see them."

GOAL_LINE = "{done} of {goal} ({pct}%)"
GOAL_REACHED = "Goal reached!"
GOAL_ETA = "At the pace of the last 7 days (≈ {per_day} per day) it is reached on {date}"
GOAL_NO_PACE_ZERO = "No responses in the last 7 days: cannot estimate"
GOAL_NO_PACE_ENOUGH = "Not enough pace to estimate when it will be reached"
GOAL_SECTION = "Goals"
GOAL_BLOCK_TITLE = "Goal"
HOME_GOALS_EMPTY = "You have not set any goals yet. You can set one for each survey with “Edit”."

# Summary: pace and question crossing
RHYTHM_TITLE = "Pace"
RHYTHM_WEEK = "This week: {n} {word}"
RHYTHM_WEEK_DELTA = " ({delta} vs the previous one)"
RHYTHM_WEEK_NOTE = "The comparison with the previous week uses all saved responses, regardless of the chosen period."
RHYTHM_PEAK = "Busiest day: {day} · Peak hour: {hour}:00"
RHYTHM_NO_PEAK = "There is no data yet to see the busiest day and hour."
RHYTHM_COMPLETION = "Completed the survey: {pct}%"
RHYTHM_WEEKDAYS_TITLE = "Responses by day of the week"
RHYTHM_HOURS_TITLE = "Responses by hour of the day"
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

CROSS_TITLE = "Cross questions"
CROSS_HELP = "See how those who chose an option answered the other questions. Works with choice questions."
CROSS_QUESTION = "Question"
CROSS_OPTION = "Option"
CROSS_APPLY = "Apply"
CROSS_CLEAR = "Remove filter"
CROSS_RIBBON = "Showing {matched} of {total} people who answered “{option}” in “{question}”"
CROSS_NOBODY = "Nobody chose that option in this period."
CROSS_EXPORT_NOTE = "Exports still use all the responses of the period."
CROSS_NO_QUESTIONS = "This survey has no choice questions to cross."
CROSS_SELF_NOTE = "The filtered question shows 100% on the chosen option: that is expected."

# Notifications
SEC_NOTIFY = "Notifications"
NOTIFY_CHECK = "Notify me when there are new responses"
NOTIFY_INTERVAL_LABEL = "Check every:"
NOTIFY_INTERVALS = [("15", "15 minutes"), ("30", "30 minutes"), ("60", "1 hour"), ("360", "6 hours")]
NOTIFY_NOTE = ("While the app is open (also minimized), the list of your surveys is checked in Tally every so often "
               "and, if there are new unsaved responses, you get a system notification. It only counts surveys that are "
               "not archived. If the connection fails, nothing is notified and it retries on the next cycle.")
NOTIFY_NO_TRAY = "Your system does not offer a tray"
NOTIFY_TRAY_OPEN, NOTIFY_TRAY_QUIT = "Open", "Quit"
NOTIFY_TRAY_TITLE = "Close to the tray"
NOTIFY_TRAY_TEXT = ("The app will keep running in the tray to notify you. To close it completely: right click → Quit.")
NOTIFY_TRAY_TOOLTIP = "Tally Monitor"

# ---------- formats according to the language ----------
DATE_FMT = "%m/%d/%Y"
DATETIME_FMT = "%m/%d/%Y %H:%M"
DATETIME_SEC_FMT = "%m/%d/%Y %H:%M:%S"
TL_HOUR_FMT, TL_DAY_FMT, TL_MONTH_FMT = "%m/%d %H:00", "%m/%d", "%m/%Y"
QT_DATE_FMT = "MM/dd/yyyy"
DECIMAL_SEP, THOUSANDS_SEP = ".", ","
PCT_FMT = "{value}%"

# ---------- relative times and durations ----------
REL_NEVER, REL_NOW = "never", "just now"
REL_MIN, REL_HOUR = "{n} min ago", "{n} h ago"
REL_DAY_ONE, REL_DAY_MANY = "{n} day ago", "{n} days ago"
DUR_SECONDS, DUR_SECOND_ONE = "{n} seconds", "1 second"
DUR_MINUTES, DUR_ONE_MINUTE = "{n} minutes", "1 minute"
DUR_HOUR_ONE, DUR_HOUR_MANY, DUR_AND_MINUTES = "{n} hour", "{n} hours", " and {n} minutes"

# ---------- texts built by the presenters ----------
ACCOUNT_DEFAULT_NAME = "Account {n}"
ACCOUNT_VALIDATED_REL = "validated {when}"
ACCOUNT_NOT_VALIDATED = "not validated yet"
SURVEY_SAVED_ONE, SURVEY_SAVED_MANY = "{n} response saved", "{n} responses saved"
SURVEY_SYNCED_REL = "synced {when}"
SURVEY_REPORTED_ONE, SURVEY_REPORTED_MANY = " · Tally reports {n} response", " · Tally reports {n} responses"
SYNC_RESULT_NOCHANGE = "No changes: you already had all the responses."
SYNC_RESULT_INITIAL_ONE, SYNC_RESULT_INITIAL_MANY = "Downloaded {n} response.", "Downloaded {n} responses."
SYNC_RESULT_NEW_ONE, SYNC_RESULT_NEW_MANY = "{n} new response.", "{n} new responses."
SYNC_RESULT_NONE_NEW = "No new responses."
SYNC_RESULT_FULL = "Full sync: {new} new, {updated} already existed."
SYNC_RESULT_FULL_MISSING = "Full sync: {new} new, {updated} already existed, {missing} are no longer in Tally."
SYNC_RESULT_MISMATCH = " Warning: {local} are saved and Tally reports {remote}."
OTHER_ITEM, OTHER_ITEM_TIMES, OTHER_MORE = "“{text}”", "“{text}” ×{n}", "and {n} more"
RHYTHM_WORD_ONE, RHYTHM_WORD_MANY = "response", "responses"
HOUR_LABEL = "{h}:00"
SYNC_PROGRESS, SYNC_PROGRESS_OF = "{label}: {done}…", "{label}: {done} of {total}…"
PERIOD_LABEL = "Period: {label}"
CUSTOM_RANGE = "{start} to {end}"
PERIOD_WITH_INCOMPLETE, PERIOD_WITHOUT_INCOMPLETE = "{label} · with incomplete submissions", "{label} · without incomplete submissions"

# ---------- account messages ----------
ACCOUNT_ADDED = "Account “{name}” added and validated."
ACCOUNT_VALIDATE_RESULT = "“{name}”: {message}"
ACCOUNT_RENAMED = "Account renamed to “{name}”."
ACCOUNT_DELETED = "Account “{name}” deleted."
KEY_FORMAT_ERROR = "The API Key does not have the expected format: it must start with “tly-” and contain no spaces."
NAME_LENGTH_ERROR = "The name must be between 1 and 60 characters."

# ---------- accessible names and widget labels ----------
OPEN_SUFFIX = "Open"
STATUS_ACCESSIBLE = "Status: {label}"
THEME_ACCESSIBLE = "{label} theme"
API_KEY_FIELD = "API Key"
BAR_CHART_NAME = "Bar chart"
RED_DOT_NAME = "Has responses not up to date"
TIMELINE_NAME = "Responses over time chart"
TIMELINE_DESC = "{total} responses in {n} intervals"

# ---------- export (PNG image) ----------
EXPORT_PNG_SUBTITLE = "{label} · {n} responses"
EXPORT_PNG_IND_SUBTITLE = "{n} individual responses · {period}"
EXPORT_PNG_INCOMPLETE = " · incomplete"

# ---------- language ----------
SEC_LANGUAGE = "Idioma / Language"
LANGUAGE_LABEL = "Idioma / Language:"
LANGUAGE_NAMES = [("es", "Español"), ("en", "English")]
LANGUAGE_RESTART = "Reiniciá la aplicación para aplicar el cambio / Restart the app to apply the change"

# ---------- Home greetings ----------
GREET_SPECIAL = {
    (12, 24): ("Merry Christmas!", "Christmas surveys? See how they are doing."),
    (12, 25): ("Merry Christmas!", "Christmas surveys? See how they are doing."),
    (12, 31): ("Last day of the year", "A look back at your surveys before the toast?"),
    (1, 1): ("Happy New Year!", "Start the year by seeing how your surveys are kicking off."),
    (2, 14): ("Valentine's Day", "A survey about love? Asking costs nothing."),
    (5, 1): ("Labor Day", "Today is a day off, but responses keep coming in."),
    (5, 25): ("Happy May 25!", "A national holiday in Argentina: a good day to see what people think."),
    (7, 9): ("Happy Independence Day (Argentina)!", "A great date for an opinion survey."),
    (7, 20): ("Happy Friend's Day!", "Did you send the survey to your friends?"),
    (10, 31): ("Happy Halloween!", "Scary surveys? Check for mysterious responses."),
}
GREET_BETWEEN_HOLIDAYS = ("Between Christmas and New Year", "A slow week: a good time to review results.")
GREET_NIGHT, GREET_MORNING = "Up late with your surveys", "Good morning!"
GREET_AFTERNOON, GREET_EVENING = "Good afternoon!", "Good evening!"
GREET_WEEKDAY = (       # Monday = 0
    "The week has started: let's see how the surveys are going.",
    "Tuesday numbers: how many responses came in?",
    "Midweek. How are the surveys doing?",
    "Thursday: almost the weekend. Any news?",
    "Friday: one last look before the weekend.",
    "Saturday: checking surveys anyway? I like it.",
    "Easy Sunday. Surveys never get tired.",
)
