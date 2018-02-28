import sys

from numbers import Number
from pathlib import Path
from datetime import datetime
from logging import getLogger

try:
    from . import config
except ImportError as e:
    raise ImportError('Please copy config.example.py to config.py and customize it.') from e

sequence = (tuple, list)
path = (str, Path)
set_sequence = (tuple, list, set, frozenset)
set_sequence_range = (tuple, list, range, set, frozenset)

worker_count = config.GRID[0] * config.GRID[1]

_valid_types = {
    'ACCOUNTS': set_sequence,
    'ACCOUNTS_CSV': path,
    'ALT_PRECISION': int,
    'ALT_RANGE': sequence,
    'ALWAYS_NOTIFY': int,
    'ALWAYS_NOTIFY_IDS': set_sequence_range,
    'APP_SIMULATION': bool,
    'AREA_NAME': str,
    'AUTHKEY': bytes,
    'BOOTSTRAP_RADIUS': Number,
    'BOUNDARIES': object,
    'CACHE_CELLS': bool,
    'CAPTCHAS_ALLOWED': int,
    'CAPTCHA_KEY': str,
    'COMPLETE_TUTORIAL': bool,
    'COROUTINES_LIMIT': int,
    'DATETIME_FORMAT_SPEC': str,
    'DATETIME_RANGE_FORMAT': str,
    'DB': dict,
    'DB_ENGINE': str,
    'DIRECTORY': path,
    'DISCORD_INVITE_ID': str,
    'DISCORD_RAID_AVATAR': str,
    'DISCORD_RAID_CONTENT': str,
    'DISCORD_RAID_DATA': dict,
    'DISCORD_RAID_EMBED_AUTHOR': str,
    'DISCORD_RAID_EMBED_DESC': str,
    'DISCORD_RAID_EMBED_IMAGE': str,
    'DISCORD_RAID_EMBED_THUMBNAIL': str,
    'DISCORD_RAID_EMBED_TITLE': str,
    'DISCORD_RAID_USERNAME': str,
    'DISCORD_RAID_EGG_AVATAR': str,
    'DISCORD_RAID_EGG_CONTENT': str,
    'DISCORD_RAID_EGG_DATA': dict,
    'DISCORD_RAID_EGG_EMBED_AUTHOR': str,
    'DISCORD_RAID_EGG_EMBED_DESC': str,
    'DISCORD_RAID_EGG_EMBED_IMAGE': str,
    'DISCORD_RAID_EGG_EMBED_THUMBNAIL': str,
    'DISCORD_RAID_EGG_EMBED_TITLE': str,
    'DISCORD_RAID_EGG_USERNAME': str,
    'DISCORD_SPAWN_AVATAR': str,
    'DISCORD_SPAWN_CONTENT': str,
    'DISCORD_SPAWN_DATA': dict,
    'DISCORD_SPAWN_EMBED_AUTHOR': str,
    'DISCORD_SPAWN_EMBED_DESC': str,
    'DISCORD_SPAWN_EMBED_IMAGE': str,
    'DISCORD_SPAWN_EMBED_THUMBNAIL': str,
    'DISCORD_SPAWN_EMBED_TITLE': str,
    'DISCORD_SPAWN_USERNAME': str,
    'DISCORD_URL': str,
    'DURATION_RANGE_FORMAT': str,
    'EMULATE_LEGACY_RARITY_BUGS': bool,
    'ENCOUNTER': str,
    'ENCOUNTER_IDS': set_sequence_range,
    'FAILURES_ALLOWED': int,
    'FAVOR_CAPTCHA': bool,
    'FB_PAGE_ID': str,
    'FIXED_OPACITY': bool,
    'FORCED_KILL': bool,
    'FULL_TIME': Number,
    'GENDER_SYMBOLS': dict,
    'GENDER_TEXT': dict,
    'GIVE_UP_KNOWN': Number,
    'GIVE_UP_UNKNOWN': Number,
    'GOOD_ENOUGH': Number,
    'GOOGLE_MAPS_KEY': str,
    'GRID': sequence,
    'HASHTAGS': set_sequence,
    'HASH_KEY': (str,) + set_sequence,
    'HEATMAP': bool,
    'IGNORE_IVS': bool,
    'IGNORE_RARITY': bool,
    'IGNORE_SENDER_TEST': bool,
    'IMAGE_STATS': bool,
    'INCUBATE_EGGS': bool,
    'INITIAL_SCORE': Number,
    'ITEM_LIMITS': dict,
    'IV_FONT': str,
    'LANDMARKS': object,
    'LANGUAGE': str,
    'LAST_MIGRATION': Number,
    'LOAD_CUSTOM_CSS_FILE': bool,
    'LOAD_CUSTOM_HTML_FILE': bool,
    'LOAD_CUSTOM_JS_FILE': bool,
    'LOGIN_TIMEOUT': Number,
    'LURE_DURATION': Number,
    'MANAGER_ADDRESS': (str, tuple, list),
    'MAP_END': sequence,
    'MAP_FILTER_IDS': sequence,
    'MAP_PROVIDER_ATTRIBUTION': str,
    'MAP_PROVIDER_URL': str,
    'MAP_START': sequence,
    'MAP_WORKERS': bool,
    'MAX_CAPTCHAS': int,
    'MAX_RETRIES': int,
    'MINIMUM_RUNTIME': Number,
    'MINIMUM_SCORE': Number,
    'MORE_POINTS': bool,
    'MOVE_FONT': str,
    'NAME_FONT': str,
    'NAV_URL_FORMAT': str,
    'NEVER_NOTIFY_IDS': set_sequence_range,
    'NON_NESTING_IDS': set_sequence_range,
    'NOTIFY': (bool, object),
    'NOTIFY_DEFAULT_CONNECT_TIMEOUT': Number,
    'NOTIFY_DEFAULT_READ_TIMEOUT': Number,
    'NOTIFY_IDS': set_sequence_range,
    'NOTIFY_RAIDS': bool,
    'NOTIFY_RANKING': int,
    'PASS': str,
    'PB_API_KEY': str,
    'PB_CHANNEL': (int, str),
    'PLAYER_LOCALE': dict,
    'PROVIDER': str,
    'PROXIES': set_sequence,
    'PUSHBULLET_API_KEY': str,
    'PUSHBULLET_CHANNEL': str,
    'PUSHBULLET_RAID_EGG_BODY': str,
    'PUSHBULLET_RAID_EGG_TITLE': str,
    'PUSHBULLET_RAID_BODY': str,
    'PUSHBULLET_RAID_TITLE': str,
    'PUSHBULLET_SPAWN_BODY': str,
    'PUSHBULLET_SPAWN_TITLE': str,
    'RAIDS_FILTER': set_sequence_range,
    'RAIDS_LVL_MIN': int,
    'RAIDS_IDS': set_sequence_range,
    'RAIDS_DISCORD_URL': str,
    'RARE_IDS': set_sequence_range,
    'RARITY_OVERRIDE': dict,
    'REFRESH_RATE': Number,
    'REPORT_MAPS': bool,
    'REPORT_SINCE': datetime,
    'RESCAN_UNKNOWN': Number,
    'SCAN_DELAY': Number,
    'SEARCH_SLEEP': Number,
    'SHOW_TIMER': bool,
    'SHOW_TIMER_RAIDS': bool,
    'SIMULTANEOUS_LOGINS': int,
    'SIMULTANEOUS_SIMULATION': int,
    'SKIP_SPAWN': Number,
    'SMART_THROTTLE': Number,
    'SMTP_ATTACH': bool,
    'SMTP_FROM': str,
    'SMTP_HOST': str,
    'SMTP_PASSWORD': str,
    'SMTP_PORT': int,
    'SMTP_RAID_EGG_SUBJECT': str,
    'SMTP_RAID_EGG_TEXT': str,
    'SMTP_RAID_SUBJECT': str,
    'SMTP_RAID_TEXT': str,
    'SMTP_SPAWN_SUBJECT': str,
    'SMTP_SPAWN_TEXT': str,
    'SMTP_STARTTLS': bool,
    'SMTP_TIMEOUT': Number,
    'SMTP_TLS': bool,
    'SMTP_TO': (str, tuple, list, set, frozenset),
    'SMTP_USERNAME': str,
    'SPAWN_ID_INT': bool,
    'SPEED_LIMIT': Number,
    'SPEED_UNIT': str,
    'SPIN_COOLDOWN': Number,
    'SPIN_POKESTOPS': bool,
    'STAT_REFRESH': Number,
    'STAY_WITHIN_MAP': bool,
    'SWAP_OLDEST': Number,
    'TELEGRAM_BOT_TOKEN': str,
    'TELEGRAM_CHAT_ID': str,
    'TELEGRAM_MESSAGE_TYPE': (int, str),
    'TELEGRAM_RAIDS_CHAT_ID': str,
    'TELEGRAM_RAID_EGG_TEXT': str,
    'TELEGRAM_RAID_EGG_VENUE': str,
    'TELEGRAM_RAID_TEXT': str,
    'TELEGRAM_RAID_VENUE': str,
    'TELEGRAM_SPAWN_TEXT': str,
    'TELEGRAM_SPAWN_VENUE': str,
    'TELEGRAM_TEXT_PARSER': str,
    'TELEGRAM_USERNAME': str,
    'TIME_REQUIRED': Number,
    'TRASH_IDS': set_sequence_range,
    'TWEET_IMAGES': bool,
    'TWITTER_ACCESS_KEY': str,
    'TWITTER_ACCESS_SECRET': str,
    'TWITTER_CONSUMER_KEY': str,
    'TWITTER_CONSUMER_SECRET': str,
    'TWITTER_RAID_EGG_FORMATS': sequence,
    'TWITTER_RAID_FORMATS': sequence,
    'TWITTER_SCREEN_NAME': str,
    'TWITTER_SPAWN_FORMATS': sequence,
    'TWITTER_TEXT_LIMIT': int,
    'TZ_OFFSET': Number,
    'UVLOOP': bool,
    'WEBHOOKS': set_sequence,
    'WEBHOOK_TIMEOUT': Number,
    'WEBHOOK_VERIFY_TLS': bool,
}

_defaults = {
    'ACCOUNTS': None,
    'ACCOUNTS_CSV': None,
    'ALT_PRECISION': 2,
    'ALT_RANGE': (300, 400),
    'ALWAYS_NOTIFY': 0,
    'ALWAYS_NOTIFY_IDS': set(),
    'APP_SIMULATION': True,
    'AREA_NAME': 'Area',
    'AUTHKEY': b'm3wtw0',
    'BOOTSTRAP_RADIUS': 120,
    'BOUNDARIES': None,
    'CACHE_CELLS': False,
    'CAPTCHAS_ALLOWED': 3,
    'CAPTCHA_KEY': None,
    'COMPLETE_TUTORIAL': False,
    'CONTROL_SOCKS': None,
    'COROUTINES_LIMIT': worker_count,
    'DATETIME_FORMAT_SPEC': "%X",
    'DATETIME_RANGE_FORMAT': "between {min} and {max}",
    'DIRECTORY': '.',
    'DISCORD_INVITE_ID': None,
    'DISCORD_RAID_EGG_AVATAR': None,
    'DISCORD_RAID_EGG_CONTENT': None,
    'DISCORD_RAID_EGG_DATA': None,
    'DISCORD_RAID_EGG_EMBED_AUTHOR': None,
    'DISCORD_RAID_EGG_EMBED_DESC': "Hatches at {start:%H:%M} ({eggremain!d})\nEnds at {end:%H:%M} ({remain!d})\nGym Control: {team}",
    'DISCORD_RAID_EGG_EMBED_IMAGE': "https://maps.googleapis.com/maps/api/staticmap?language={config.LANGUAGE}&size=250x125&zoom=15&markers={lat:.5f},{lon:.5f}",
    'DISCORD_RAID_EGG_EMBED_THUMBNAIL': "https://raw.githubusercontent.com/ZeChrales/monocle-icons/larger-outlined/larger-icons/0.png",
    'DISCORD_RAID_EGG_EMBED_TITLE': "T{tier} Raid Egg at {fortname}",
    'DISCORD_RAID_EGG_USERNAME': "T{tier} Raid Egg",
    'DISCORD_RAID_AVATAR': None,
    'DISCORD_RAID_CONTENT': None,
    'DISCORD_RAID_DATA': None,
    'DISCORD_RAID_EMBED_AUTHOR': None,
    'DISCORD_RAID_EMBED_DESC': "Ends at {end:%H:%M} ({remain!d})\nGym Control: {team}\n{move1}/{move2}",
    'DISCORD_RAID_EMBED_IMAGE': "https://maps.googleapis.com/maps/api/staticmap?language={config.LANGUAGE}&size=250x125&zoom=15&markers={lat:.5f},{lon:.5f}",
    'DISCORD_RAID_EMBED_THUMBNAIL': "https://raw.githubusercontent.com/ZeChrales/monocle-icons/larger-outlined/larger-icons/{dexno}.png",
    'DISCORD_RAID_EMBED_TITLE': "{name} Raid at {fortname}",
    'DISCORD_RAID_USERNAME': "{name} Raid",
    'DISCORD_SPAWN_AVATAR': None,
    'DISCORD_SPAWN_CONTENT': None,
    'DISCORD_SPAWN_DATA': None,
    'DISCORD_SPAWN_EMBED_AUTHOR': None,
    'DISCORD_SPAWN_EMBED_DESC': "[{attack}/{defense}/{stamina}] {gender} {move1}/{move2}\nUntil {untilrange}",
    'DISCORD_SPAWN_EMBED_IMAGE': "https://maps.googleapis.com/maps/api/staticmap?language={config.LANGUAGE}&size=250x125&zoom=15&markers={lat:.5f},{lon:.5f}",
    'DISCORD_SPAWN_EMBED_THUMBNAIL': None,
    'DISCORD_SPAWN_EMBED_TITLE': "{name} - {pplace}",
    'DISCORD_SPAWN_USERNAME': "{name} {iv}%",
    'DISCORD_URL': None,
    'DURATION_RANGE_FORMAT': "between {min} and {max}",
    'EMULATE_LEGACY_RARITY_BUGS': False,
    'ENCOUNTER': None,
    'ENCOUNTER_IDS': None,
    'FAVOR_CAPTCHA': True,
    'FAILURES_ALLOWED': 2,
    'FB_PAGE_ID': None,
    'FIXED_OPACITY': False,
    'FORCED_KILL': None,
    'FULL_TIME': 1800,
    'GENDER_SYMBOLS': {1: "♂", 2: "♀", 3: "⚲"},
    'GENDER_TEXT': {1: "male", 2: "female", 3: "genderless"},
    'GIVE_UP_KNOWN': 75,
    'GIVE_UP_UNKNOWN': 60,
    'GOOD_ENOUGH': 0.1,
    'GOOGLE_MAPS_KEY': '',
    'HASHTAGS': None,
    'IGNORE_IVS': False,
    'IGNORE_RARITY': False,
    'IGNORE_SENDER_TEST': False,
    'IMAGE_STATS': False,
    'INCUBATE_EGGS': True,
    'INITIAL_RANKING': None,
    'ITEM_LIMITS': None,
    'IV_FONT': 'monospace',
    'LANDMARKS': None,
    'LANGUAGE': 'EN',
    'LAST_MIGRATION': 1481932800,
    'LOAD_CUSTOM_CSS_FILE': False,
    'LOAD_CUSTOM_HTML_FILE': False,
    'LOAD_CUSTOM_JS_FILE': False,
    'LOGIN_TIMEOUT': 2.5,
    'LURE_DURATION': 1800,
    'MANAGER_ADDRESS': None,
    'MAP_FILTER_IDS': None,
    'MAP_PROVIDER_URL': '//{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    'MAP_PROVIDER_ATTRIBUTION': '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    'MAP_WORKERS': True,
    'MAX_CAPTCHAS': 0,
    'MAX_RETRIES': 3,
    'MINIMUM_RUNTIME': 10,
    'MORE_POINTS': False,
    'MOVE_FONT': 'sans-serif',
    'NAME_FONT': 'sans-serif',
    'NAV_URL_FORMAT': 'https://www.google.com/maps?q={lat:.5f},{lon:.5f}',
    'NEVER_NOTIFY_IDS': (),
    'NON_NESTING_IDS': (),
    'NOTIFY': False,
    'NOTIFY_DEFAULT_CONNECT_TIMEOUT': 7,
    'NOTIFY_DEFAULT_READ_TIMEOUT': 30,
    'NOTIFY_RAIDS': False,
    'NOTIFY_IDS': None,
    'NOTIFY_RANKING': None,
    'PASS': None,
    'PB_API_KEY': None,
    'PB_CHANNEL': None,
    'PLAYER_LOCALE': {'country': 'US', 'language': 'en', 'timezone': 'America/Denver'},
    'PROVIDER': None,
    'PROXIES': None,
    'PUSHBULLET_API_KEY': None,
    'PUSHBULLET_CHANNEL': None,
    'PUSHBULLET_RAID_EGG_BODY': "{fortname}\nHatches at {start:%H:%M} ({eggremain!d})\nEnds at {end:%H:%M} ({remain!d})\nGym Control: {team}",
    'PUSHBULLET_RAID_EGG_TITLE': "T{tier} Raid Egg",
    'PUSHBULLET_RAID_BODY': "{fortname}\nEnds at {end:%H:%M} ({remain!d})\nGym Control: {team}\n{move1}/{move2}",
    'PUSHBULLET_RAID_TITLE': "{name} Raid",
    'PUSHBULLET_SPAWN_BODY': "It will be there until {untilrange} ({remainrange}).\n\nAttack: {attack}\nDefense: {defense}\nStamina: {stamina}\n{move1}/{move2}\n",
    'PUSHBULLET_SPAWN_TITLE': "A {rating} {name} appeared {pplace}!",
    'RAIDS_FILTER': (1, 2, 3, 4, 5),
    'RAIDS_LVL_MIN': None,
    'RAIDS_IDS': (),
    'RAIDS_DISCORD_URL': None,
    'RARE_IDS': (),
    'RARITY_OVERRIDE': {},
    'REFRESH_RATE': 0.6,
    'REPORT_MAPS': True,
    'REPORT_SINCE': None,
    'RESCAN_UNKNOWN': 90,
    'SCAN_DELAY': 10,
    'SEARCH_SLEEP': 2.5,
    'SHOW_TIMER': False,
    'SHOW_TIMER_RAIDS': False,
    'SIMULTANEOUS_LOGINS': 2,
    'SIMULTANEOUS_SIMULATION': 4,
    'SKIP_SPAWN': 90,
    'SMART_THROTTLE': False,
    'SMTP_ATTACH': False,
    'SMTP_FROM': 'monocle@example.com',
    'SMTP_HOST': 'localhost',
    'SMTP_PASSWORD': None,
    'SMTP_PORT': 587,
    'SMTP_RAID_EGG_SUBJECT': "T{tier} Raid Egg",
    'SMTP_RAID_EGG_TEXT': "{fortname}\nHatches at {start:%H:%M} ({eggremain!d})\nEnds at {end:%H:%M} ({remain!d})\nGym Control: {team}\n{navurl}",
    'SMTP_RAID_SUBJECT': "{name} Raid",
    'SMTP_RAID_TEXT': "{fortname}\nEnds at {end:%H:%M} ({remain!d})\nGym Control: {team}\n{move1}/{move2}\n{navurl}",
    'SMTP_SPAWN_SUBJECT': "{name} {iv}%",
    'SMTP_SPAWN_TEXT': "[{attack},{defense},{stamina}] {gender} {move1}/{move2}\nUntil {untilrange}\n{navurl}",
    'SMTP_STARTTLS': False,
    'SMTP_TIMEOUT': 30,
    'SMTP_TLS': False,
    'SMTP_TO': [],
    'SMTP_USERNAME': None,
    'SPAWN_ID_INT': True,
    'SPEED_LIMIT': 19.5,
    'SPEED_UNIT': 'miles',
    'SPIN_COOLDOWN': 300,
    'SPIN_POKESTOPS': True,
    'STAT_REFRESH': 5,
    'STAY_WITHIN_MAP': True,
    'SWAP_OLDEST': 21600 / worker_count,
    'TELEGRAM_BOT_TOKEN': None,
    'TELEGRAM_CHAT_ID': None,
    'TELEGRAM_MESSAGE_TYPE': 'venue',
    'TELEGRAM_RAIDS_CHAT_ID': None,
    'TELEGRAM_RAID_EGG_TEXT': "T{tier} Raid Egg",
    'TELEGRAM_RAID_EGG_VENUE': "Hatches at {start:%H:%M} ({eggremain!d}) {team}",
    'TELEGRAM_RAID_TEXT': "{name} Raid",
    'TELEGRAM_RAID_VENUE': "Ends at {end:%H:%M} ({remain!d}) {team}",
    'TELEGRAM_SPAWN_TEXT': "{name} ({attack}/{defense}/{stamina})",
    'TELEGRAM_SPAWN_VENUE': "Expires: {untilrange}",
    'TELEGRAM_TEXT_PARSER': None,
    'TELEGRAM_USERNAME': None,
    'TIME_REQUIRED': 300,
    'TRASH_IDS': (),
    'TWEET_IMAGES': False,
    'TWITTER_ACCESS_KEY': None,
    'TWITTER_ACCESS_SECRET': None,
    'TWITTER_CONSUMER_KEY': None,
    'TWITTER_CONSUMER_SECRET': None,
    'TWITTER_RAID_EGG_FORMATS': [
        "T{tier} Raid Egg at {fortname} ({team}) hatches at {start:%H:%M}, ends at {end:%H:%M} {navurl}",
        "T{tier} Raid Egg at {fortname} ({team}) hatches at {start:%H:%M} {navurl}",
        "T{tier} Raid Egg ({team}) hatches at {start:%H:%M} {navurl}",
        ],
    'TWITTER_RAID_FORMATS': [
        "{name} Raid at {fortname} ({team}) {move1}/{move2} ends at {end:%H:%M} {navurl}",
        "{name} Raid at {fortname} ({team}) ends at {end:%H:%M} {navurl}",
        "{name} Raid ({team}) ends at {end:%H:%M} {navurl}",
        ],
    'TWITTER_SCREEN_NAME': None,
    'TWITTER_SPAWN_FORMATS': [
        "A {rating} {name} appeared! It will be {pplace} until {untilrange}. {hashtags} {navurl}",
        "A {rating} {name} appeared! It will be {pplaceshort} until {untilrange}. {hashtags} {navurl}",
        "A {rating} {name} will be {pplaceshort} until {untilrange}. {navurl}",
        "A {rating} {name} will expire at {untilmin}. {navurl}",
        "{name} {pplaceshort} until {untilrange} {navurl}",
        "{name} until {untilrange} {navurl}",
        ],
    'TWITTER_TEXT_LIMIT': 280,
    'TZ_OFFSET': None,
    'UVLOOP': True,
    'WEBHOOKS': None,
    'WEBHOOK_TIMEOUT': 4,
    'WEBHOOK_VERIFY_TLS': True,
}


class Config:
    __spec__ = __spec__
    __slots__ = tuple(_valid_types.keys()) + ('log',)

    def __init__(self):
        self.log = getLogger('sanitizer')
        for key, value in (x for x in vars(config).items() if x[0].isupper()):
            try:
                if isinstance(value, _valid_types[key]):
                    setattr(self, key, value)
                    if key in _defaults:
                        del _defaults[key]
                elif key in _defaults and value is _defaults[key]:
                    setattr(self, key, _defaults.pop(key))
                else:
                    valid = _valid_types[key]
                    actual = type(value).__name__
                    if isinstance(valid, type):
                        err = '{} must be {}. Yours is: {}.'.format(
                            key, valid.__name__, actual)
                    else:
                        types = ', '.join((x.__name__ for x in valid))
                        err = '{} must be one of {}. Yours is: {}'.format(
                            key, types, actual)
                    raise TypeError(err)
            except KeyError:
                self.log.warning('{} is not a valid config option'.format(key))

    def __getattr__(self, name):
        try:
            default = _defaults.pop(name)
            setattr(self, name, default)
            return default
        except KeyError:
            if name == '__path__':
                return
            err = '{} not in config, and no default has been set.'.format(name)
            self.log.error(err)
            raise AttributeError(err)

sys.modules[__name__] = Config()

del _valid_types, config
