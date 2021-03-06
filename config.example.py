### All lines that are commented out (and some that aren't) are optional ###

DB_ENGINE = 'sqlite:///db.sqlite'
#DB_ENGINE = 'mysql://user:pass@localhost/monocle'
#DB_ENGINE = 'postgresql://user:pass@localhost/monocle'

AREA_NAME = 'SLC'     # the city or region you are scanning
LANGUAGE = 'EN'       # ISO 639-1 codes EN, DE, ES, FR, IT, JA, KO, PT, or ZH for Pokémon/move names
MAX_CAPTCHAS = 100    # stop launching new visits if this many CAPTCHAs are pending
SCAN_DELAY = 10       # wait at least this many seconds before scanning with the same account
SPEED_UNIT = 'miles'  # valid options are 'miles', 'kilometers', 'meters'
SPEED_LIMIT = 19.5    # limit worker speed to this many SPEED_UNITs per hour

# The number of simultaneous workers will be these two numbers multiplied.
# On the initial run, workers will arrange themselves in a grid across the
# rectangle you defined with MAP_START and MAP_END.
# The rows/columns will also be used for the dot grid in the console output.
# Provide more accounts than the product of your grid to allow swapping.
GRID = (4, 4)  # rows, columns

# the corner points of a rectangle for your workers to spread out over before
# any spawn points have been discovered
MAP_START = (40.7913, -111.9398)
MAP_END = (40.7143, -111.8046)

# do not visit spawn points outside of your MAP_START and MAP_END rectangle
# the boundaries will be the rectangle created by MAP_START and MAP_END, unless
STAY_WITHIN_MAP = True

# ensure that you visit within this many meters of every part of your map during bootstrap
# lower values are more thorough but will take longer
BOOTSTRAP_RADIUS = 120

GIVE_UP_KNOWN = 75   # try to find a worker for a known spawn for this many seconds before giving up
GIVE_UP_UNKNOWN = 60 # try to find a worker for an unknown point for this many seconds before giving up
SKIP_SPAWN = 90      # don't even try to find a worker for a spawn if the spawn time was more than this many seconds ago

# How often should the mystery queue be reloaded (default 90s)
# this will reduce the grouping of workers around the last few mysteries
#RESCAN_UNKNOWN = 90

# filename of accounts CSV
ACCOUNTS_CSV = 'accounts.csv'

# the directory that the pickles folder, socket, CSV, etc. will go in
# defaults to working directory if not set
#DIRECTORY = None

# Limit the number of simultaneous logins to this many at a time.
# Lower numbers will increase the amount of time it takes for all workers to
# get started but are recommended to avoid suddenly flooding the servers with
# accounts and arousing suspicion.
SIMULTANEOUS_LOGINS = 4

# Limit the number of workers simulating the app startup process simultaneously.
SIMULTANEOUS_SIMULATION = 10

# Immediately select workers whose speed are below (SPEED_UNIT)p/h instead of
# continuing to try to find the worker with the lowest speed.
# May increase clustering if you have a high density of workers.
GOOD_ENOUGH = 0.1

# Seconds to sleep after failing to find an eligible worker before trying again.
SEARCH_SLEEP = 2.5

## alternatively define a Polygon to use as boundaries (requires shapely)
## if BOUNDARIES is set, STAY_WITHIN_MAP will be ignored
## more information available in the shapely manual:
## http://toblerity.org/shapely/manual.html#polygons
#from shapely.geometry import Polygon
#BOUNDARIES = Polygon(((40.799609, -111.948556), (40.792749, -111.887341), (40.779264, -111.838078), (40.761410, -111.817908), (40.728636, -111.805293), (40.688833, -111.785564), (40.689768, -111.919389), (40.750461, -111.949938)))

# key for Bossland's hashing server, otherwise the old hashing lib will be used
#HASH_KEY = '9d87af14461b93cb3605'  # this key is fake

# Skip PokéStop spinning and egg incubation if your request rate is too high
# for your hashing subscription.
# e.g.
#   75/150 hashes available 35/60 seconds passed => fine
#   70/150 hashes available 30/60 seconds passed => throttle (only scan)
# value: how many requests to keep as spare (0.1 = 10%), False to disable
#SMART_THROTTLE = 0.1

# Swap the worker that has seen the fewest Pokémon every x seconds
# Defaults to whatever will allow every worker to be swapped within 6 hours
#SWAP_OLDEST = 300  # 5 minutes
# Only swap if it's been active for more than x minutes
#MINIMUM_RUNTIME = 10

### these next 6 options use more requests but look more like the real client
APP_SIMULATION = True     # mimic the actual app's login requests
COMPLETE_TUTORIAL = True  # complete the tutorial process and configure avatar for all accounts that haven't yet
INCUBATE_EGGS = True      # incubate eggs if available

## encounter Pokémon to store IVs.
## valid options:
# 'all' will encounter every Pokémon that hasn't been already been encountered
# 'some' will encounter Pokémon if they are in ENCOUNTER_IDS or eligible for notification
# 'notifying' will encounter Pokémon that are eligible for notifications
# None will never encounter Pokémon
ENCOUNTER = None
#ENCOUNTER_IDS = (3, 6, 9, 45, 62, 71, 80, 85, 87, 89, 91, 94, 114, 130, 131, 134)

# PokéStops
SPIN_POKESTOPS = True  # spin all PokéStops that are within range
SPIN_COOLDOWN = 300    # spin only one PokéStop every n seconds (default 300)
LURE_DURATION = 1800 # lure duration (default 30mn)

# minimum number of each item to keep if the bag is cleaned
# bag cleaning is disabled if this is not present or is commented out
''' # triple quotes are comments, remove them to use this ITEM_LIMITS example
ITEM_LIMITS = {
    1:    20,  # Poké Ball
    2:    50,  # Great Ball
    3:   100,  # Ultra Ball
    101:   0,  # Potion
    102:   0,  # Super Potion
    103:   0,  # Hyper Potion
    104:  40,  # Max Potion
    201:   0,  # Revive
    202:  40,  # Max Revive
    701:  20,  # Razz Berry
    702:  20,  # Bluk Berry
    703:  20,  # Nanab Berry
    704:  20,  # Wepar Berry
    705:  20,  # Pinap Berry
}
'''

# Update the console output every x seconds
REFRESH_RATE = 0.75  # 750ms
# Update the seen/speed/visit/speed stats every x seconds
STAT_REFRESH = 5

# sent with GET_PLAYER requests, should match your region
PLAYER_LOCALE = {'country': 'US', 'language': 'en', 'timezone': 'America/Denver'}

# retry a request after failure this many times before giving up
MAX_RETRIES = 3

# number of seconds before timing out on a login request
LOGIN_TIMEOUT = 2.5

# add spawn points reported in cell_ids to the unknown spawns list
#MORE_POINTS = False

# Set to True to kill the scanner when a newer version is forced
#FORCED_KILL = False

# exclude these Pokémon from the map by default (only visible in trash layer)
TRASH_IDS = (
    16, 19, 21, 29, 32, 41, 46, 48, 50, 52, 56, 74, 77, 96, 111, 133,
    161, 163, 167, 177, 183, 191, 194
)

# include these Pokémon on the "rare" report
RARE_IDS = (3, 6, 9, 45, 62, 71, 80, 85, 87, 89, 91, 94, 114, 130, 131, 134)

# IDs for naturally spawning Pokémon known not to nest
NON_NESTING_IDS = (2,3,5,6,8,9,11,12,14,15,17,18,20,22,24,  # Gen 1
                   26,28,30,31,33,34,36,38,40,42,44,45,47,
                   49,51,53,55,57,59,61,62,64,65,67,68,70,
                   71,73,75,76,78,80,82,83,85,87,88,89,91,
                   93,94,97,99,101,103,105,106,107,108,109,
                   110,112,113,114,115,117,119,121,122,128,
                   129,130,131,132,134,135,136,137,139,141,
                   142,143,147,148,149,
                   153,154,156,157,159,160,162,164,166,168, # Gen 2
                   169,171,176,178,179,180,181,184,185,188,
                   189,195,198,201,204,205,207,210,214,217,
                   219,221,222,224,225,226,227,229,231,232,
                   234,237,241,242,246,247,248,
                   253,256,259,262,264,270,271,274,277,279, # Gen 3
                   280,281,284,286,287,288,294,297,301,302,
                   305,311,312,313,314,315,317,319,323,324,
                   326,328,329,331,332,334,335,336,337,338,
                   340,342,344,345,346,347,348,349,351,354,
                   356,357,358,361,362,363,364,369,371,372,
                   374,375
)

from datetime import datetime
REPORT_SINCE = datetime(2017, 2, 17)  # base reports on data from after this date

# used for altitude queries and maps in reports
#GOOGLE_MAPS_KEY = 'OYOgW1wryrp2RKJ81u7BLvHfYUA6aArIyuQCXu4'  # this key is fake
REPORT_MAPS = True  # Show maps on reports
#ALT_RANGE = (1250, 1450)  # Fall back to altitudes in this range if Google query fails

## Round altitude coordinates to this many decimal places
## More precision will lead to larger caches and more Google API calls
## Maximum distance from coords to rounded coords for precisions (at Lat40):
## 1: 7KM, 2: 700M, 3: 70M, 4: 7M
#ALT_PRECISION = 2

## Automatically resolve captchas using 2Captcha key.
#CAPTCHA_KEY = '1abc234de56fab7c89012d34e56fa7b8'
## the number of CAPTCHAs an account is allowed to receive before being swapped out
#CAPTCHAS_ALLOWED = 3
## Get new accounts from the CAPTCHA queue first if it's not empty
#FAVOR_CAPTCHA = True

# allow displaying the live location of workers on the map
MAP_WORKERS = True
# filter these Pokemon from the map to reduce traffic and browser load
#MAP_FILTER_IDS = [161, 165, 16, 19, 167]

# unix timestamp of last spawn point migration, spawn times learned before this will be ignored
LAST_MIGRATION = 1481932800  # Dec. 17th, 2016

# Treat a spawn point's expiration time as unknown if nothing is seen at it on more than x consecutive visits
FAILURES_ALLOWED = 2

## Map data provider and appearance, previews available at:
## https://leaflet-extras.github.io/leaflet-providers/preview/
#MAP_PROVIDER_URL = '//{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
#MAP_PROVIDER_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

# set of proxy addresses and ports
# SOCKS requires aiosocks to be installed
#PROXIES = {'http://127.0.0.1:8080', 'https://127.0.0.1:8443', 'socks5://127.0.0.1:1080'}

# convert spawn_id to integer for more efficient DB storage, set to False if
# using an old database since the data types are incompatible.
#SPAWN_ID_INT = True

# Bytestring key to authenticate with manager for inter-process communication
#AUTHKEY = b'm3wtw0'
# Address to use for manager, leave commented if you're not sure.
#MANAGER_ADDRESS = r'\\.\pipe\monocle'  # must be in this format for Windows
#MANAGER_ADDRESS = 'monocle.sock'       # the socket name for Unix systems
#MANAGER_ADDRESS = ('127.0.0.1', 5002)  # could be used for CAPTCHA solving and live worker maps on remote systems

# Store the cell IDs so that they don't have to be recalculated every visit.
# Enabling will (potentially drastically) increase memory usage.
#CACHE_CELLS = False

# Only for use with web_sanic (requires PostgreSQL)
#DB = {'host': '127.0.0.1', 'user': 'monocle_role', 'password': 'pik4chu', 'port': '5432', 'database': 'monocle'}

# Disable to use Python's event loop even if uvloop is installed
#UVLOOP = True

# The number of coroutines that are allowed to run simultaneously.
#COROUTINES_LIMIT = GRID[0] * GRID[1]

### FRONTEND CONFIGURATION
LOAD_CUSTOM_HTML_FILE = False # File path MUST be 'templates/custom.html'
LOAD_CUSTOM_CSS_FILE = False  # File path MUST be 'static/css/custom.css'
LOAD_CUSTOM_JS_FILE = False   # File path MUST be 'static/js/custom.js'

#FB_PAGE_ID = None
#TWITTER_SCREEN_NAME = None  # Username withouth '@' char
#DISCORD_INVITE_ID = None
#TELEGRAM_USERNAME = None  # Username withouth '@' char

## Variables below will be used as default values on frontend
#RAIDS_FILTER = (1, 2, 3, 4, 5)  # Levels shown by default on map
FIXED_OPACITY = False  # Make marker opacity independent of remaining time
SHOW_TIMER = False  # Show remaining time on a label under each pokemon marker
SHOW_TIMER_RAIDS = True  # Show remaining time on a label under each raid marker

###
### OPTIONS BELOW THIS POINT ARE ONLY NECESSARY FOR NOTIFICATIONS ###
###

from .notifyconfig import *
NOTIFY = NotifyConfig()

NOTIFY.enable(False)

###
### Rule-Based Notifications & Channels
### See the documentation in notifyconfig.py for more information on these.
###

# Tyranitar & Machamp raids
#NOTIFY.raid(['tyranitar', 'machamp'], True)
# Tier-5 raids and raid eggs of any species
#NOTIFY.raid(..., [tier >= 5])

# Good first-gen starter spawns
#NOTIFY.spawn(['bulbasaur', 'charmander', 'squirtle'], [iv > 80, attack >= 14])
# Dragonite family spawns
#NOTIFY.spawn(['dratini', 'dragonair', 'Dragonite'], True)
# Perfect-IV spawns of any species
#NOTIFY.spawn(..., [iv == 100])

# Named notification channels have their own recipients and rules
#NOTIFY.senders(DiscordConfig(URL="https://discordapp.com/api/webhooks/123/xx"), channel='private')
#NOTIFY.spawn({'Unown'}, True, channel='private')
#NOTIFY.senders(SMTPConfig(TO=['bob@example.com']), channel='koga')
#NOTIFY.spawn({'pidgeotto'}, [iv == 100], [iv == 0], channel='koga')

###
### Score-Based Spawn Notifications
###

# the required number of seconds remaining for score-based spawn notifications
TIME_REQUIRED = 600  # 10 minutes

### Only set either the NOTIFY_RANKING or NOTIFY_IDS, not both!
# The (x) rarest Pokémon will be eligible for notification. Whether a
# notification is sent or not depends on its score, as explained below.
#NOTIFY_RANKING = 90

# Pokémon to potentially notify about, in order of preference.
# The first in the list will have a rarity score of 1, the last will be 0.
#NOTIFY_IDS = (130, 89, 131, 3, 9, 134, 62, 94, 91, 87, 71, 45, 85, 114, 80, 6)

# Spawns of the top (x) will always notify, even if below TIME_REQUIRED
# (ignored if using NOTIFY_IDS instead of NOTIFY_RANKING)
#ALWAYS_NOTIFY = 14

# Always notify about the following Pokémon even if their time remaining or scores are not high enough
#ALWAYS_NOTIFY_IDS = {89, 130, 144, 145, 146, 150, 151}

# Never notify about the following Pokémon, even if they would otherwise be eligible
#NEVER_NOTIFY_IDS = TRASH_IDS

# Override the rarity score for particular Pokémon
# format is: {pokemon_id: rarity_score}
#RARITY_OVERRIDE = {148: 0.6, 149: 0.9}

# Ignore IV score and only base decision on rarity score (default if IVs not known)
#IGNORE_IVS = False

# Ignore rarity score and only base decision on IV score
#IGNORE_RARITY = False

# The Pokémon score required to notify goes on a sliding scale from INITIAL_SCORE
# to MINIMUM_SCORE over the course of FULL_TIME seconds following a notification
# Pokémon scores are an average of the Pokémon's rarity score and IV score (from 0 to 1)
# If NOTIFY_RANKING is 90, the 90th most common Pokémon will have a rarity of score 0, the rarest will be 1.
# IV score is the IV sum divided by 45 (perfect IVs).
FULL_TIME = 1800  # the number of seconds after a notification when only MINIMUM_SCORE will be required
INITIAL_SCORE = 0.7  # the required score immediately after a notification
MINIMUM_SCORE = 0.4  # the required score after FULL_TIME seconds have passed

# Emulate rarity-related bugs that were in the old notification module
#EMULATE_LEGACY_RARITY_BUGS = True


# create images with Pokémon image and optionally include IVs and moves
# requires cairo and ENCOUNTER = 'notifying' or 'all'
TWEET_IMAGES = False
# IVs and moves are now dependant on level, so this is probably not useful
IMAGE_STATS = False

# As many hashtags as can fit will be included in your tweets, these will
# be combined with landmark-specific hashtags (if applicable).
HASHTAGS = {AREA_NAME, 'Monocle', 'PokemonGO'}

#TZ_OFFSET = 0  # UTC offset in hours (if different from system time)

### Field format for datetime values in notification messages
#DATETIME_FORMAT_SPEC = "%X"

### String format for datetime ranges in notification messages
### These field names will have values: {min}, {mid}, {max}, {margin}
#DATETIME_RANGE_FORMAT = "between {min} and {max}"

### String format for duration ranges in notification messages
### These field names will have values: {min}, {mid}, {max}, {margin}
#DURATION_RANGE_FORMAT = "between {min} and {max}"

### Gender symbols & text for each gender number
#GENDER_SYMBOLS = {1: "♂", 2: "♀", 3: "⚲"}
#GENDER_TEXT = {1: "male", 2: "female", 3: "genderless"}

### Navigation URL format, for spawn notifications
#NAV_URL_FORMAT = 'https://maps.google.com/maps?q={lat:.5f},{lon:.5f}'


###
### Notification Senders
###

### The credentials below are fake. Replace them with your own keys to
### enable notifications, or leave them commented out.
### You must configure at least one sender in order to use notifications.

### A Discord webhook URL can be created in Discord channel settings.  Example:
### https://discordapp.com/api/webhooks/<webhook_id>/<webhook_token>
###
#DISCORD_URL = "https://discordapp.com/api/webhooks/1234567890/xxxxxxxx"
###
### The following format strings can override Discord webhook defaults:
### WARNING: Using the static map URLs below will expose your google maps key.
###
#DISCORD_RAID_EGG_USERNAME = ""
#DISCORD_RAID_EGG_AVATAR = "https://raw.githubusercontent.com/ZeChrales/monocle-icons/larger-outlined/larger-icons/0.png"
#DISCORD_RAID_EGG_CONTENT = ""
#DISCORD_RAID_EGG_EMBED_AUTHOR = ""
#DISCORD_RAID_EGG_EMBED_DESC "Hatches at {start:%H:%M} ({eggremain!d})\nEnds at {end:%H:%M} ({remain!d})\nGym Control: {team}\n{place}"
#DISCORD_RAID_EGG_EMBED_IMAGE = "https://maps.googleapis.com/maps/api/staticmap?key={config.GOOGLE_MAPS_KEY}&language={config.LANGUAGE}&size=250x125&zoom=15&markers={lat:.5f},{lon:.5f}"
#DISCORD_RAID_EGG_EMBED_THUMBNAIL = "https://raw.githubusercontent.com/ZeChrales/monocle-icons/larger-outlined/larger-icons/0.png"
#DISCORD_RAID_EGG_EMBED_TITLE = "T{tier} Raid Egg at {fortname}"
#DISCORD_RAID_USERNAME = ""
#DISCORD_RAID_AVATAR = "https://raw.githubusercontent.com/ZeChrales/monocle-icons/larger-outlined/larger-icons/{dexno}.png"
#DISCORD_RAID_CONTENT = ""
#DISCORD_RAID_EMBED_AUTHOR = ""
#DISCORD_RAID_EMBED_DESC = "Ends at {end:%H:%M} ({remain!d})\nGym Control: {team}\n{move1}/{move2}"
#DISCORD_RAID_EMBED_IMAGE = "https://maps.googleapis.com/maps/api/staticmap?key={config.GOOGLE_MAPS_KEY}&language={config.LANGUAGE}&size=250x125&zoom=15&markers={lat:.5f},{lon:.5f}"
#DISCORD_RAID_EMBED_THUMBNAIL = "https://raw.githubusercontent.com/ZeChrales/monocle-icons/larger-outlined/larger-icons/{dexno}.png"
#DISCORD_RAID_EMBED_TITLE = "{name} Raid at {fortname}"
#DISCORD_SPAWN_USERNAME = ""
#DISCORD_SPAWN_AVATAR = "https://raw.githubusercontent.com/ZeChrales/monocle-icons/larger-outlined/larger-icons/{dexno}.png"
#DISCORD_SPAWN_CONTENT = ""
#DISCORD_SPAWN_EMBED_AUTHOR = ""
#DISCORD_SPAWN_EMBED_TITLE = "{name} - {pplace}"
#DISCORD_SPAWN_EMBED_DESC = "[{attack}/{defense}/{stamina}] {gender} {move1}/{move2}\nUntil {untilrange}"
#DISCORD_SPAWN_EMBED_IMAGE = "https://maps.googleapis.com/maps/api/staticmap?key={config.GOOGLE_MAPS_KEY}&language={config.LANGUAGE}&size=250x125&zoom=15&markers={lat:.5f},{lon:.5f}"
#DISCORD_SPAWN_EMBED_THUMBNAIL = "https://raw.githubusercontent.com/ZeChrales/monocle-icons/larger-outlined/larger-icons/{dexno}.png"
###
### The following dicts allow completely custom Discord webhook structures:
### https://discordapp.com/developers/docs/resources/webhook#execute-webhook
###
#DISCORD_RAID_EGG_DATA = {"content": "T{tier} Raid Egg until {start}"}
#DISCORD_RAID_DATA = {"content": "{name} Raid until {end}"}
#DISCORD_SPAWN_DATA = {"username": "{name} {iv}%", "embeds": [{"title": "{place}", "url": "{navurl}"}]}

#PUSHBULLET_API_KEY = 'o.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
#PUSHBULLET_CHANNEL = 'mytag'  # your channel tag name, or to None to push privately
#PUSHBULLET_RAID_EGG_TITLE = "T{tier} Raid Egg"
#PUSHBULLET_RAID_EGG_BODY = "{fortname}\nHatches at {start:%H:%M} ({eggremain!d})\nEnds at {end:%H:%M} ({remain!d})\nGym Control: {team}"
#PUSHBULLET_RAID_TITLE = "T{tier} Raid: {name}"
#PUSHBULLET_RAID_BODY = "{fortname}\nEnds at {end:%H:%M} ({remain!d})\nGym Control: {team}\n{move1}/{move2}"
#PUSHBULLET_SPAWN_TITLE = "{name} {iv}% ({attack}/{defense}/{stamina})"
#PUSHBULLET_SPAWN_BODY = "Until {untilrange}\n"

#SMTP_TO = ['username@example.net']
#SMTP_FROM = 'monocle@example.com'
#SMTP_HOST = 'localhost'
#SMTP_PORT = 587
#SMTP_TLS = False
#SMTP_STARTTLS = False
#SMTP_TIMEOUT = 30
#SMTP_USERNAME = None
#SMTP_PASSWORD = None
#SMTP_RAID_EGG_SUBJECT = "T{tier} Raid Egg"
#SMTP_RAID_EGG_TEXT = "{fortname}\nHatches at {start:%H:%M} ({eggremain!d})\nEnds at {end:%H:%M} ({remain!d})\nGym Control: {team}\n{navurl}"
#SMTP_RAID_SUBJECT = "T{tier} Raid: {name}"
#SMTP_RAID_TEXT = "{fortname}\nEnds at {end:%H:%M} ({remain!d})\nGym Control: {team}\n{move1}/{move2}\n{navurl}"
#SMTP_SPAWN_SUBJECT = "{name} {iv}%"
#SMTP_SPAWN_TEXT = "[{attack},{defense},{stamina}] {gender} {move1}/{move2}\nUntil {untilrange}\n{navurl}"
#SMTP_ATTACH = False

### Telegram bot token is the one Botfather sends to you after creating a bot.
### CHAT_ID can be any of these:
### 1) '@channel_name' for public channels.
### 2) The channel's chat_id for private channels.
###    This is a 13-digit negative number, formed by prepending "-100" to the
###    channel id, which can be retrieved using https://github.com/vysheng/tg
###    or found in the channel's web.telegram.org URL (between the 'c' and '_').
###    Details here:  https://github.com/GabrielRF/telegram-id
### 3) Your chat_id if you will be sending messages to your own account.
###    To retrieve your ID, write to your bot and check this URL:
###    https://api.telegram.org/bot<BOT_TOKEN_HERE>/getUpdates
###
#TELEGRAM_BOT_TOKEN = '123456789:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
#TELEGRAM_CHAT_ID = '@your_channel'
###
### By default, Telegram notifications are sent as venue messages, composed of
### (for spawns) TELEGRAM_SPAWN_TEXT, TELEGRAM_SPAWN_VENUE, and an embedded
### location.  By setting TELEGRAM_MESSAGE_TYPE = 'text' instead of 'venue',
### you can have messages composed only of TELEGRAM_SPAWN_TEXT, with optional
### support for styled text (TELEGRAM_TEXT_PARSER = 'Markdown' or 'HTML').
###
#TELEGRAM_MESSAGE_TYPE = 'text'
#TELEGRAM_RAID_EGG_TEXT = "T{tier} Raid Egg\n{fortname}\nHatches at {start:%H:%M} ({eggremain!d})\nEnds at {end:%H:%M} ({remain!d})\nGym Control: {team}\n{navurl}"
#TELEGRAM_RAID_EGG_VENUE = "Hatch: {start:%H:%M}\n{fortname}\nGym Control: {team}"
#TELEGRAM_RAID_TEXT = "{name} Raid\n{fortname}\nEnds at {end:%H:%M} ({remain!d})\nGym Control: {team}\n{move1}/{move2}\n{navurl}"
#TELEGRAM_RAID_VENUE = "End: {end:%H:%M}\n{fortname}\nGym Control: {team}"
#TELEGRAM_SPAWN_TEXT = "{name} {iv}% ({attack}/{defense}/{stamina})\nExpires: {untilrange}\n{navurl}"
#TELEGRAM_SPAWN_VENUE = "Expires: {untilrange}\n{navurl}"
#TELEGRAM_TEXT_PARSER = 'Markdown'

#TWITTER_CONSUMER_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxx'
#TWITTER_CONSUMER_SECRET = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
#TWITTER_ACCESS_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
#TWITTER_ACCESS_SECRET = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
#TWITTER_RAID_EGG_FORMATS = ["T{tier} Raid Egg ({team}) hatches at {start:%H:%M} {navurl}"]
#TWITTER_RAID_FORMATS = ["{name} Raid ({team}) ends at {end:%H:%M} {navurl}"]
#TWITTER_SPAWN_FORMATS = ["{name} {pplaceshort} until {untilrange} {navurl}"]

#WEBHOOK_TIMEOUT = 4
#WEBHOOK_VERIFY_TLS = True
#WEBHOOKS = {'http://127.0.0.1:4000'}


##### Referencing landmarks in your tweets/notifications

#### It is recommended to store the LANDMARKS object in a pickle to reduce startup
#### time if you are using queries. An example script for this is in:
#### scripts/pickle_landmarks.example.py
#from pickle import load
#with open('pickles/landmarks.pickle', 'rb') as f:
#    LANDMARKS = load(f)

### if you do pickle it, just load the pickle and omit everything below this point

#from monocle.landmarks import Landmarks
#LANDMARKS = Landmarks(query_suffix=AREA_NAME)

# Landmarks to reference when Pokémon are nearby
# If no points are specified then it will query OpenStreetMap for the coordinates
# If 1 point is provided then it will use those coordinates but not create a shape
# If 2 points are provided it will create a rectangle with its corners at those points
# If 3 or more points are provided it will create a polygon with vertices at each point
# You can specify the string to search for on OpenStreetMap with the query parameter
# If no query or points is provided it will query with the name of the landmark (and query_suffix)
# Optionally provide a set of hashtags to be used for tweets about this landmark
# Use is_area for neighborhoods, regions, etc.
# When selecting a landmark, non-areas will be chosen first if any are close enough
# the default phrase is 'in' for areas and 'at' for non-areas, but can be overriden for either.

### replace these with well-known places in your area

## since no points or query is provided, the names provided will be queried and suffixed with AREA_NAME
#LANDMARKS.add('Rice Eccles Stadium', shortname='Rice Eccles', hashtags={'Utes'})
#LANDMARKS.add('the Salt Lake Temple', shortname='the temple', hashtags={'TempleSquare'})

## provide two corner points to create a square for this area
#LANDMARKS.add('City Creek Center', points=((40.769210, -111.893901), (40.767231, -111.888275)), hashtags={'CityCreek'})

## provide a query that is different from the landmark name so that OpenStreetMap finds the correct one
#LANDMARKS.add('the State Capitol', shortname='the Capitol', query='Utah State Capitol Building')

### area examples ###
## query using name, override the default area phrase so that it says 'at (name)' instead of 'in'
#LANDMARKS.add('the University of Utah', shortname='the U of U', hashtags={'Utes'}, phrase='at', is_area=True)
## provide corner points to create a polygon of the area since OpenStreetMap does not have a shape for it
#LANDMARKS.add('Yalecrest', points=((40.750263, -111.836502), (40.750377, -111.851108), (40.751515, -111.853833), (40.741212, -111.853909), (40.741188, -111.836519)), is_area=True)
