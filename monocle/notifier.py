"""
Event notifications via external messaging services.

"""

import asyncio
from asyncio import gather, wait_for
import bisect
from collections import namedtuple, ChainMap, UserDict
import contextlib
from datetime import datetime, timedelta, timezone
from email.mime.application import MIMEApplication
from email.mime.audio import MIMEAudio
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import enum
import functools
from io import BytesIO
import itertools
from pathlib import PurePosixPath
import string
from time import monotonic, time
import traceback
from typing import Container, Sequence
from urllib.parse import urlsplit

import aiohttp
import aiohttp.client
try:
    import aiosmtplib
except ImportError:
    aiosmtplib = None
try:
    import asyncpushbullet
except ImportError:
    asyncpushbullet = None
try:
    import cairo  #pylint:disable=no-member
except ImportError:
    cairo = None
try:
    import peony
    import peony.exceptions
except ImportError:
    peony = None
from pkg_resources import resource_string
from sqlalchemy.exc import SQLAlchemyError
try:
    from ujson import dumps as json_dumps
except ImportError:
    from json import dumps as json_dumps

from . import db
from . import names
from . import notifyconfig
from . import sanitized as conf
from .shared import get_logger, run_threaded
from . import utils

#pylint:disable=too-many-lines


class _AsyncLogExceptionsContext:
    """Async context manager for selectively suppressing / logging exceptions.
    """
    def __init__(self, name, suppress, quiet):
        """Save logger name & desired exception behavior.

        :param name:        A logger name.
        :type  name:        str
        :param suppress:    Exception type(s) to suppress.
        :type  suppress:    Exception or tuple
        :param quiet:       Exception type(s) not to log.
        :type  quiet:       Exception or tuple
        """
        self._log = get_logger(name)
        self._suppress = suppress
        self._quiet = quiet

    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False
        if not issubclass(exc_type, self._quiet):
            self._log.error(''.join(
                traceback.format_exception(exc_type, exc_val, exc_tb)).rstrip())
        return issubclass(exc_type, self._suppress)


class exception_logging_coro:  #pylint:disable=invalid-name
    """Coroutine decorator for selectively suppressing / logging exceptions.
    Must be instantiated with a logger name.
    """
    def __init__(self, name, *, suppress=(), quiet=()):
        """See _AsyncLogExceptionsContext for argument details.
        """
        if callable(name):
            raise TypeError(self.__class__.__name__ +
                " decorator requires a logger name argument")
        self._context = _AsyncLogExceptionsContext(name, suppress, quiet)

    def __call__(self, func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):  #pylint:disable=missing-docstring
            async with self._context:
                return await func(*args, **kwargs)
        return wrapper


class _TempSet(set):
    """A set with automatic item removal via context manger.

    Usage:
        items = _TempSet(loop=asyncio.get_event_loop())
        with items.temp_add('foo'):
            pass                # Discard 'foo' when the context ends
        with items.temp_add('bar') as tentative:
            tentative.keep(30)  # Keep 'bar' for 30 seconds
    """
    def __init__(self, *args, loop, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop = loop

    def temp_add(self, item):
        """Return a context manager for adding and later discarding an item.
        """
        return self._Manager(self, item, loop=self.loop)

    class _Manager:
        """Context manager for adding and discarding items.
        Items are added when the context begins.
        Items are discarded when the context ends,
        or some time afterward if keep() is called.
        """
        def __init__(self, items, item, loop):
            self._items = items
            self.item = item
            self.delay = 0
            self.loop = loop

        def keep(self, seconds):
            """Delay discarding the item for a while after the context ends.
            """
            self.delay = seconds

        def __enter__(self):
            if self.item in self._items:
                raise ValueError("duplicate item: " + repr(self.item))
            self._items.add(self.item)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.delay:
                self.loop.call_later(self.delay, self._items.discard, self.item)
            else:
                self._items.discard(self.item)


class MapTimeOfDay(enum.IntEnum):
    """A time_of_day value from a pgoapi get_map_objects response.
    """
    NONE = 0
    DAY = 1
    NIGHT = 2


class Attachment:
    """Represents a message attachment.

    Currently only supports data in memory (not files) because file I/O would
    block coroutines.  If the aiofiles package (or similar) ever adds support
    for temporary files, it might make sense to use it for file attachments.
    Until then, non-blocking file access would require writing our own code to
    quarantine it all (including calls to libraries that use files) in separate
    threads.  That would be a lot of needless complexity just to send small
    images or log excerpts, and it would be easy to forget and accidentally
    block coroutines.  Therefore, we use an in-memory interface for now.
    We can use BytesIO for APIs that expect file-like objects.
    """
    def __init__(self, data, mimetype):
        """Save an attachment's content type and data.

        :type data:         bytes-like object
        :type mimetype:     str
        """
        self.data = data
        self.mimetype = mimetype


class _HashTagSet(set):
    """A set with twitter-style hashtag string formatting.
    """
    def __format__(self, format_spec):
        return ' '.join('#' + str(tag) for tag in self)


class _EventFormatter(string.Formatter):
    """Formatter with fallback text, {!d} duration format, & field use tracking.
    """
    def __init__(self):
        self.used_args = set()

    class Missing:
        "Replacement for missing values"
        def __format__(self, format_spec):
            return "?"
    _MISSING = Missing()

    def get_field(self, field_name, args, kwargs):
        "Intercept missing-value exceptions and apply a sentinel value."
        try:
            return super().get_field(field_name, args, kwargs)
        except (KeyError, IndexError, AttributeError):
            return (self._MISSING, None)

    @staticmethod
    def _format_timedelta(delta, format_spec):  #pylint:disable=unused-argument
        "Format a timedelta as a string."
        seconds = delta.total_seconds()
        parts = []
        for div, suffix in [(24*60*60, 'd'), (60*60, 'h'), (60, 'm'), (1, 's')]:
            num, seconds = divmod(int(seconds), div)
            if num:
                parts.append(str(num) + suffix)
        return ''.join(parts) or "0s"

    def format_field(self, value, format_spec=''):
        "Apply default formats from the config file."
        if isinstance(value, timedelta):
            return self._format_timedelta(value, format_spec)
        if isinstance(value, datetime) and not format_spec:
            format_spec = conf.DATETIME_FORMAT_SPEC
        return super().format_field(value, format_spec)

    def convert_field(self, value, conversion):
        "Preserve sentinel value.  Support {!d} for seconds as duration."
        if value is self._MISSING:
            return value
        if conversion == 'd' and isinstance(value, (int, float)):
            return timedelta(seconds=value)
        return super().convert_field(value, conversion)

    def check_unused_args(self, used_args, args, kwargs):
        "Store used_args for later reference."
        self.used_args = used_args


class Event(ChainMap):  #pylint:disable=too-many-ancestors
    """Base class for notification events.

    Exposes event details from one or more dicts via the Mapping interface.
    For convenience, dict keys can also be read as if they were attributes.

    Offers string template formatting with fallback text instead of exceptions
    for missing values.
    """
    def format(self, template):
        """Format event variables without missing-value exceptions.
        Ths works like str.format_map(event), except that missing values are
        represented as a special character rather than raising an exception.
        """
        return _EventFormatter().vformat(template, (), self)

    def format_and_tell(self, template):
        """Format event variables & report names of variables that are used.

        :return:            Formatted text and a used-variable-name set.
        :rtype:             Tuple[str, Set[str]]
        """
        formatter = _EventFormatter()
        text = formatter.vformat(template, (), self)
        return (text, formatter.used_args)

    def __getattr__(self, name):
        """Make mapping keys readable as if they were attributes.
        """
        try:
            return self[name]
        except KeyError as err:
            raise AttributeError("This {} event has no {!r} value".format(
                self.__class__.__name__, name)) from err


class Raid(Event):  #pylint:disable=too-many-ancestors
    """Raid event.
    """
    def __str__(self):
        return self['fortname'] + " raid"


class Spawn(Event):  #pylint:disable=too-many-ancestors
    """Pokemon spawn event.
    """
    def __str__(self):
        return self['name'] + " spawn"


class SenderError(Exception):
    """Common exception type for Sender failures.
    """


class Sender:
    """Base class for message senders.
    """
    # CONFIG_CLASS a subclass-specific Mapping type for holding sender settings.
    # Instances of this type are passed to and stored by __init__().
    # They are created in the config file when defining notification channels.
    # Subclasses must override this attribute with the appropriate type from
    # the notifyconfig module.
    CONFIG_CLASS = None

    @staticmethod
    def have_global_config():
        """Return True if this sender's global settings are configured.
        This signals that an instance should be created for the default channel.
        """
        raise NotImplementedError

    def __init__(self, *, loop, websession, config=None):
        """Verify dependencies & save configuration settings for later use.

        :param loop:        An asyncio event loop.
        :type  loop:        AbstractEventLoop
        :param websession:  A session object for http requests.
        :type  websession:  aiohttp.ClientSession
        :param config:      A CONFIG_CLASS instance containing sender settings.
        :type  config:      CONFIG_CLASS or None

        :raises ImportError:    If required module imports failed.
        :raises TypeError:      If config is not an instance of CONFIG_CLASS.
        :raises ValueError:     If config values are inappropriate or missing.
        """
        if not isinstance(config, (self.CONFIG_CLASS, type(None))):
            raise TypeError("{} is not an instance of {}".format(
                config, self.CONFIG_CLASS.__name__))

        self.config = dict(config) if config else dict()
        for key, globalkey in self.CONFIG_CLASS.KEYS.items():
            if key not in self.config:
                self.config[key] = getattr(conf, globalkey)

        self.log = get_logger('notifier')
        self.loop = loop
        self.websession = websession

    async def test(self):
        """Test the ability to connect & authenticate to the messaging service.

        :raises SenderError: On failure
        """
        pass

    def want_attachments(self, eventtype):
        """Return true if attachments are wanted for the given event type.

        This is a hint to calling code:  It can skip preparing attachments for
        an event if no senders indicate that they want attachments.  This is
        merely a hint inteded for use in groups of senders; callers are allowed
        to ignore the hint.  Subclasses must therefore allow & ignore any
        unsupported attachments passed to send().
        """
        #pylint:disable=no-self-use
        assert issubclass(eventtype, Event)
        return False

    async def send(self, event, attachments=()):
        """Send an event notification, optionally with attachments.

        :param event:       Details of the event.
        :type  event:       Event
        :param attachments: Attachments to include in the notification.
                            Subclasses should ignore attachments if they are
                            not enabled in the sender's config settings.
        :type  attachments: Iterable[Attachment]

        :raises KeyError(Event):    On unsuppoted event type.
        :raises SenderError:        On failure
        """
        raise NotImplementedError

    async def close(self):
        """Close any open connections.

        :raises SenderError: on failure
        """

    def __str__(self):
        """Return a string to identify the sender in log messages.
        """
        return self.__class__.__name__.replace('Sender', '')


class DiscordSender(Sender):
    """Discord sender.
    """
    CONFIG_CLASS = notifyconfig.DiscordConfig

    # Related:  https://discordapp.com/developers/docs/resources/webhook

    @staticmethod
    def have_global_config():
        """Return True if this sender's global settings are configured.
        This will cause an instance to be created for the default channel.
        """
        return bool(conf.DISCORD_URL)

    def __init__(self, *, loop, websession, config=None):

        super().__init__(loop=loop, websession=websession, config=config)

        try:
            urlpath = PurePosixPath(urlsplit(self.config['URL']).path)
            self._hookid = urlpath.parts[3]
            self._token = urlpath.parts[4]
        except IndexError:
            self.log.warning("DISCORD_URL format looks invalid.")
            self._hookid = "(unknown format)"
            self._token = None

    async def test(self):
        """Test connectivity and auth token.
        """
        await self._call('GET')

    async def send(self, event, attachments=()):
        """Send an event notification, ignoring attachments.
        """
        data = self._MESSAGE_MAKERS[type(event)](event)
        await self._call('POST', self._format_data(data, event))

    async def _call(self, method, data=None):
        """Call a Discord webhook method with JSON-encoded dict data.

        :raises SenderError: on failure
        """
        try:
            async with self.websession.request(method, self.config['URL'],
                json=data):
                pass
        except aiohttp.ClientResponseError as err:
            raise SenderError(err.code, err.message, data) from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise SenderError(type(err), *self._sanitize_err_args(err)) from err

    def _sanitize_err_args(self, err):
        """Iterate over an exception's arguments, with credentials redacted.
        """
        for arg in err.args:
            if isinstance(arg, str) and self._token and self._token in arg:
                yield arg.replace(self._token, "<TOKEN>")
            else:
                yield arg

    @classmethod
    def _format_data(cls, data, event):
        "Copy a dict. Format str values. Omit empty str/sequence values."
        if isinstance(data, str):
            return event.format(data)
        if isinstance(data, dict):
            pairs = [(k, cls._format_data(v, event)) for k, v in data.items()]
            return dict((k, v) for k, v in pairs
                if v or isinstance(v, (int, float)))
        if isinstance(data, Sequence):
            values = [cls._format_data(v, event) for v in data]
            return [v for v in values if v or isinstance(v, (int, float))]
        return data

    @staticmethod
    def _make_raid_data(event):
        """Return data suitable for reporting a Raid event.
        """
        if 'dexno' in event:
            if conf.DISCORD_RAID_DATA:
                return conf.DISCORD_RAID_DATA

            return dict(
                username=conf.DISCORD_RAID_USERNAME,
                avatar_url=conf.DISCORD_RAID_AVATAR,
                content=conf.DISCORD_RAID_CONTENT,
                embeds=[
                    dict(
                        url="{navurl}",
                        author=dict(name=conf.DISCORD_RAID_EMBED_AUTHOR),
                        title=conf.DISCORD_RAID_EMBED_TITLE,
                        description=conf.DISCORD_RAID_EMBED_DESC,
                        thumbnail=dict(url=conf.DISCORD_RAID_EMBED_THUMBNAIL),
                        image=dict(url=conf.DISCORD_RAID_EMBED_IMAGE),
                        ),
                    ],
                )

        if conf.DISCORD_RAID_EGG_DATA:
            return conf.DISCORD_RAID_EGG_DATA

        return dict(
            username=conf.DISCORD_RAID_EGG_USERNAME,
            avatar_url=conf.DISCORD_RAID_EGG_AVATAR,
            content=conf.DISCORD_RAID_EGG_CONTENT,
            embeds=[
                dict(
                    url="{navurl}",
                    author=dict(name=conf.DISCORD_RAID_EGG_EMBED_AUTHOR),
                    title=conf.DISCORD_RAID_EGG_EMBED_TITLE,
                    description=conf.DISCORD_RAID_EGG_EMBED_DESC,
                    thumbnail=dict(url=conf.DISCORD_RAID_EGG_EMBED_THUMBNAIL),
                    image=dict(url=conf.DISCORD_RAID_EGG_EMBED_IMAGE),
                    ),
                ],
            )

    @staticmethod
    def _make_spawn_data(_):
        """Return data suitable for reporting a Spawn event.
        """
        if conf.DISCORD_SPAWN_DATA:
            return conf.DISCORD_SPAWN_DATA

        return dict(
            username=conf.DISCORD_SPAWN_USERNAME,
            avatar_url=conf.DISCORD_SPAWN_AVATAR,
            content=conf.DISCORD_SPAWN_CONTENT,
            embeds=[
                dict(
                    url="{navurl}",
                    author=dict(name=conf.DISCORD_SPAWN_EMBED_AUTHOR),
                    title=conf.DISCORD_SPAWN_EMBED_TITLE,
                    description=conf.DISCORD_SPAWN_EMBED_DESC,
                    thumbnail=dict(url=conf.DISCORD_SPAWN_EMBED_THUMBNAIL),
                    image=dict(url=conf.DISCORD_SPAWN_EMBED_IMAGE),
                    ),
                ],
            )

    _MESSAGE_MAKERS = {
        Raid: _make_raid_data.__func__,
        Spawn: _make_spawn_data.__func__,
        }

    def __str__(self):
        return "Discord webhook " + self._hookid


class PushbulletSender(Sender):
    """Pushbullet sender.
    """
    CONFIG_CLASS = notifyconfig.PushbulletConfig

    @staticmethod
    def have_global_config():
        """Return True if this sender's global settings are configured.
        This will cause an instance to be created for the default channel.
        """
        return bool(conf.PUSHBULLET_API_KEY or conf.PB_API_KEY)

    def __init__(self, *, loop, websession, config=None):

        if not asyncpushbullet:
            raise ImportError(
                "Pushbullet is configured but asyncpushbullet is not installed")

        super().__init__(loop=loop, websession=websession, config=config)

        # Accept legacy settings for the default channel
        if config is None and not self.config['API_KEY'] and conf.PB_API_KEY:
            self.log.warning(
                "The PB_API_KEY and PB_CHANNEL settings are deprecated. "
                "Use PUSHBULLET_API_KEY and PUSHBULLET_CHANNEL instead.")
            self.config['API_KEY'] = conf.PB_API_KEY
            self.config['CHANNEL'] = conf.PB_CHANNEL

        self._client = asyncpushbullet.AsyncPushbullet(
            api_key=self.config['API_KEY'], loop=self.loop)
        self._channel = None

    async def _load_channel(self):
        """Make sure we have a Pushbullet channel object, if configured.

        :raises SenderError: on failure
        """
        chanid = self.config['CHANNEL']
        if self._channel or chanid is None:
            return

        # Find channel by index (legacy configs only)
        if isinstance(chanid, int):
            self.log.warning(
                "Pushbullet channel numbers are deprecated. Use tags instead.")
            try:
                await self._client.async_get_channel('')  # Populate the list
                self._channel = self._client.channels[chanid]
                return
            except asyncpushbullet.PushbulletError as err:
                raise SenderError(type(err), *err.args) from err
            except IndexError:
                raise SenderError("Unknown Pushbullet channel: " + str(chanid))

        # Find channel by tag
        try:
            self._channel = await self._client.async_get_channel(chanid)
            if not self._channel:
                raise SenderError("Unknown Pushbullet channel: " + chanid)
        except asyncpushbullet.PushbulletError as err:
            raise SenderError(type(err), *err.args) from err

    async def test(self):
        """Test the ability to connect & authenticate to Pushbullet.
        """
        try:
            await self._client.async_verify_key()
        except asyncpushbullet.PushbulletError as err:
            raise SenderError(type(err), *err.args) from err

        await self._load_channel()

    async def send(self, event, attachments=()):
        """Send an event notification, optionally with attachments.
        """
        await self._load_channel()

        try:
            templates = self._MESSAGE_MAKERS[type(event)](event)

            await self._client.async_push_link(
                title=event.format(templates.title),
                url=event.format(templates.url) or None,
                body=event.format(templates.body),
                channel=self._channel)

        except asyncpushbullet.PushbulletError as err:
            raise SenderError(type(err), *err.args) from err

    # Pushbullet templates
    _TemplateGroup = namedtuple('_TemplateGroup', 'title body url')

    @staticmethod
    def _make_raid_data(event):
        """Return message templates for reporting a Raid event.
        """
        if 'dexno' in event:
            return PushbulletSender._TemplateGroup(
                title=conf.PUSHBULLET_RAID_TITLE,
                body=conf.PUSHBULLET_RAID_BODY,
                url="{navurl}")
        return PushbulletSender._TemplateGroup(
            title=conf.PUSHBULLET_RAID_EGG_TITLE,
            body=conf.PUSHBULLET_RAID_EGG_BODY,
            url="{navurl}")

    @staticmethod
    def _make_spawn_data(_):
        """Return message templates for reporting a Spawn event.
        """
        return PushbulletSender._TemplateGroup(
            title=conf.PUSHBULLET_SPAWN_TITLE,
            body=conf.PUSHBULLET_SPAWN_BODY,
            url="{navurl}")

    _MESSAGE_MAKERS = {
        Raid: _make_raid_data.__func__,
        Spawn: _make_spawn_data.__func__,
        }

    async def close(self):
        """Close any open connections.

        :raises SenderError: on failure
        """
        try:
            await self._client.close()
        except asyncpushbullet.PushbulletError as err:
            raise SenderError(type(err), *err.args) from err


if aiosmtplib:
    class _SMTPConn(aiosmtplib.SMTP):
        """SMTP context manager with automatic connection setup.
        """
        def __init__(self, *, loop, config):
            """Translate our SMTP settings into aiosmtplib __init__() args.

            :param loop:        An asyncio event loop.
            :type  loop:        AbstractEventLoop
            :param config:      SMTP connection configuration.
            :type  config:      Mapping
            """
            super().__init__(
                hostname=config['HOST'],
                port=config['PORT'],
                use_tls=config['TLS'],
                validate_certs=config['TLS'],
                timeout=config['TIMEOUT'],
                loop=loop)
            self.config = config

        async def connect(self):
            """Connect to the server and do post-connect setup.

            :raises aiosmtplib.SMTPException: On failure
            """
            response = await super().connect()

            if self.config['STARTTLS']:
                response = await self.starttls(validate_certs=True)

            username = self.config['USERNAME']
            password = self.config['PASSWORD']
            if username and password:
                response = await self.login(username, password)

            return response


class SMTPSender(Sender):
    """SMTP email sender.
    """
    CONFIG_CLASS = notifyconfig.SMTPConfig

    @staticmethod
    def have_global_config():
        """Return True if this sender's global settings are configured.
        This will cause an instance to be created for the default channel.
        """
        return bool(conf.SMTP_TO)

    def __init__(self, *, loop, websession, config=None):

        if not aiosmtplib:
            raise ImportError(
                "SMTP is configured but aiosmtplib is not installed")

        super().__init__(loop=loop, websession=websession, config=config)

        if 'TO' not in self.config:
            raise ValueError("Required SMTP TO address is missing")
        if isinstance(self.config['TO'], str):
            self.config['TO'] = [self.config['TO']]

    async def test(self):
        """Test the ability to connect & authenticate to the SMTP server.
        """
        try:
            async with _SMTPConn(loop=self.loop, config=self.config):
                pass
        except aiosmtplib.SMTPException as err:
            raise SenderError(type(err), *err.args) from err

    def want_attachments(self, eventtype):
        """Return true if attachments are wanted for the given event type.
        """
        return self.config['ATTACH']

    async def send(self, event, attachments=()):
        """Send an event notification, optionally with attachments.
        """
        message = self._make_message(event, attachments)

        try:
            async with _SMTPConn(loop=self.loop, config=self.config) as smtp:
                await smtp.send_message(message,
                    sender=self.config['FROM'],
                    recipients=self.config['TO'])

        except aiosmtplib.SMTPException as err:
            raise SenderError(type(err), *err.args) from err

    _MIME_MESSAGE_TYPES = {
        'application': MIMEApplication,
        'audio': MIMEAudio,
        'image': MIMEImage,
        'text': MIMEText,
        }

    @classmethod
    def _make_attachment_part(cls, attachment):
        """Create a MIMENonMultipart representing the given Attachment.
        """
        maintype, _, subtype = attachment.mimetype.lower().partition('/')
        if not subtype:
            subtype = None
        try:
            return cls._MIME_MESSAGE_TYPES[maintype](attachment.data, subtype)
        except KeyError:
            return MIMEApplication(attachment.data, 'octet-stream')

    def _make_message(self, event, attachments):
        """Generate and return an email.message.Message instance.
        """
        templates = self._MESSAGE_MAKERS[type(event)](event)
        message = MIMEText(event.format(templates.text))

        if templates.html:
            message = MIMEMultipart('alternative', _subparts=[message])
            message.attach(
                MIMEText(event.format(templates.html), 'html'))

        if self.config['ATTACH'] and attachments:
            message = MIMEMultipart(_subparts=[message])
            for attachment in attachments:
                message.attach(self._make_attachment_part(attachment))

        if templates.subject:
            message['Subject'] = event.format(templates.subject)

        message['From'] = self.config['FROM']

        # Omit the To: field because it would reveal recipients to each other.

        return message

    # Email message templates
    _TemplateGroup = namedtuple('_TemplateGroup', 'subject text html')

    @staticmethod
    def _make_raid_data(event):
        """Return message templates for reporting a Raid event.
        """
        if 'dexno' in event:
            return SMTPSender._TemplateGroup(
                subject=conf.SMTP_RAID_SUBJECT,
                text=conf.SMTP_RAID_TEXT,
                html=None)
        return SMTPSender._TemplateGroup(
            subject=conf.SMTP_RAID_EGG_SUBJECT,
            text=conf.SMTP_RAID_EGG_TEXT,
            html=None)

    @staticmethod
    def _make_spawn_data(_):
        """Return message templates for reporting a Spawn event.
        """
        return SMTPSender._TemplateGroup(
            subject=conf.SMTP_SPAWN_SUBJECT,
            text=conf.SMTP_SPAWN_TEXT,
            html=None)

    _MESSAGE_MAKERS = {
        Raid: _make_raid_data.__func__,
        Spawn: _make_spawn_data.__func__,
        }

    def __str__(self):
        return "{} to {}".format(super().__str__(),
            ", ".join(self.config['TO']))


class TelegramSender(Sender):
    """Telegram sender.
    """
    CONFIG_CLASS = notifyconfig.TelegramConfig

    # Related:  https://core.telegram.org/bots/api

    @staticmethod
    def have_global_config():
        """Return True if this sender's global settings are configured.
        This will cause an instance to be created for the default channel.
        """
        return bool(conf.TELEGRAM_BOT_TOKEN and conf.TELEGRAM_CHAT_ID)

    def __init__(self, *, loop, websession, config=None):

        super().__init__(loop=loop, websession=websession, config=config)

        if conf.TELEGRAM_MESSAGE_TYPE in {0, 1}:
            self.log.warning("TELEGRAM_MESSAGE_TYPE numbers are deprecated. "
                "Set it to 'text' or 'venue' instead.")
        elif conf.TELEGRAM_MESSAGE_TYPE not in {'text', 'venue'}:
            raise ValueError("TELEGRAM_MESSAGE_TYPE must be 'text' or 'venue'")
        if conf.TELEGRAM_TEXT_PARSER not in {'HTML', 'Markdown', None}:
            raise ValueError(
                "TELEGRAM_TEXT_PARSER must be 'HTML', 'Markdown', or None")

    async def test(self):
        """Test connectivity and auth token.
        """
        await self._call('getMe')

    async def send(self, event, attachments=()):
        """Send an event notification, ignoring attachments.
        """
        textformat, venueformat = self._MESSAGE_MAKERS[type(event)](event)
        text = event.format(textformat)
        venue = event.format(venueformat)

        if conf.TELEGRAM_MESSAGE_TYPE == 1:  # Deprecated config option
            text = text + '\n' + venue
            if 'navurl' in event:
                text += '\n\n<a href="{}">Open Map</a>'.format(event.navurl)
            method = 'sendMessage'
            data = dict(
                text=text,
                parse_mode='HTML',
                )
        elif 'lat' in event and conf.TELEGRAM_MESSAGE_TYPE in {'venue', 0}:
            method = 'sendVenue'
            data = dict(
                latitude=event.lat,
                longitude=event.lon,
                title=text,
                address=venue,
                )
        else:
            method = 'sendMessage'
            data = dict(text=text)
            if conf.TELEGRAM_TEXT_PARSER:
                data['parse_mode'] = conf.TELEGRAM_TEXT_PARSER

        data['chat_id'] = self.config['CHAT_ID']
        await self._call(method, data)

    async def _call(self, method, data=None):
        """Call a Telegram method with a JSON-encoded dict as the parameters.

        :raises SenderError: on failure
        """
        url = "https://api.telegram.org/bot{}/{}".format(
            self.config['BOT_TOKEN'], method)

        try:
            async with self.websession.post(url, json=data or {}):
                pass
        except aiohttp.ClientResponseError as err:
            raise SenderError(err.code, err.message) from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise SenderError(type(err), *self._sanitize_err_args(err)) from err

    def _sanitize_err_args(self, err):
        """Iterate over an exception's arguments, with credentials redacted.
        """
        for arg in err.args:
            if isinstance(arg, str) and self.config['BOT_TOKEN'] in arg:
                yield arg.replace(self.config['BOT_TOKEN'], "<TOKEN>")
            else:
                yield arg

    @staticmethod
    def _make_raid_data(event):
        """Return message text & venue formats for reporting a Raid event.
        """
        if 'dexno' in event:
            return conf.TELEGRAM_RAID_TEXT, conf.TELEGRAM_RAID_VENUE
        return conf.TELEGRAM_RAID_EGG_TEXT, conf.TELEGRAM_RAID_EGG_VENUE

    @staticmethod
    def _make_spawn_data(_):
        """Return message text & venue formats for reporting a Spawn event.
        """
        return conf.TELEGRAM_SPAWN_TEXT, conf.TELEGRAM_SPAWN_VENUE

    _MESSAGE_MAKERS = {
        Raid: _make_raid_data.__func__,
        Spawn: _make_spawn_data.__func__,
        }

    def __str__(self):
        return "{} to {}".format(super().__str__(), self.config['CHAT_ID'])


class TwitterSender(Sender):
    """Twitter sender.
    """
    CONFIG_CLASS = notifyconfig.TwitterConfig

    @staticmethod
    def have_global_config():
        """Return True if this sender's global settings are configured.
        This will cause an instance to be created for the default channel.
        """
        return all((conf.TWITTER_ACCESS_KEY, conf.TWITTER_ACCESS_SECRET,
            conf.TWITTER_CONSUMER_KEY, conf.TWITTER_CONSUMER_SECRET))

    def __init__(self, *, loop, websession, config=None):

        if not peony:
            raise ImportError(
                "Twitter is configured but peony-twitter is not installed")

        super().__init__(loop=loop, websession=websession, config=config)

        self._client = peony.PeonyClient(
            consumer_key=self.config['CONSUMER_KEY'],
            consumer_secret=self.config['CONSUMER_SECRET'],
            access_token=self.config['ACCESS_KEY'],
            access_token_secret=self.config['ACCESS_SECRET'],
            session=self.websession,
            loop=self.loop)

    async def test(self):
        """Test the ability to connect & authenticate to Twitter.
        """
        try:
            await self._client.setup()
        except peony.exceptions.PeonyException as err:
            raise SenderError(type(err), *err.args) from err

    def want_attachments(self, eventtype):
        """Return true if attachments are wanted for the given event type.
        """
        return self.config['IMAGES']

    async def send(self, event, attachments=()):
        """Send an event notification, optionally with attachments.
        """
        try:
            formats, data = self._MESSAGE_MAKERS[type(event)](event)
            data['status'] = self._format_status_text(formats, event)

            mediaids = []
            if self.config['IMAGES']:
                for attachment in attachments:
                    maintype, _, _ = attachment.mimetype.lower().partition('/')
                    if maintype != 'image':
                        continue
                    media = await self._client.upload_media(
                        BytesIO(attachment.data),
                        media_type=attachment.mimetype, chunked=True)
                    mediaids.append(media['media_id_string'])
            if mediaids:
                data['media_ids'] = ','.join(mediaids)

            await self._client.api.statuses.update.post(**data)

        except aiohttp.ClientResponseError as err:
            raise SenderError(err.code, err.message) from err
        except peony.exceptions.PeonyException as err:
            raise SenderError(type(err), *err.args) from err

    def _format_status_text(self, formats, event):
        """Format text for an event using one of the given formats.
        """
        # Copy the hashtags set so we can safely discard some for brevity
        hashtags = _HashTagSet(event.get('hashtags') or ())
        if hashtags:
            event = event.new_child(dict(hashtags=hashtags))

        # Try formats in order of preference until the text fits
        for template in formats:

            # Try discarding hashtags to make the text fit
            # Discard all hashtags if they don't fit using the first template
            while hashtags:
                text = event.format(template)
                if len(text) <= conf.TWITTER_TEXT_LIMIT:
                    return text
                hashtags.pop()

            text, usedvars = event.format_and_tell(template)
            if 'hashtags' in usedvars:
                text = text.replace("  ", " ")
            if len(text) <= conf.TWITTER_TEXT_LIMIT:
                return text

        self.log.error("{} sender: No text format short enough for event: {}",
            self, event)
        return "(No suitable text format found for this event. See log.)"

    @staticmethod
    def _make_raid_data(event):
        """Return text format and additional tweet data for a Raid event.
        """
        data = dict(
            lat=str(event.lat),
            long=str(event.lon),
            display_coordinates=True
            )
        if 'dexno' in event:
            return conf.TWITTER_RAID_FORMATS, data
        return conf.TWITTER_RAID_EGG_FORMATS, data

    @staticmethod
    def _make_spawn_data(event):
        """Return text format and additional tweet data for a Spawn event.
        """
        return conf.TWITTER_SPAWN_FORMATS, dict(
            lat=str(event.lat),
            long=str(event.lon),
            display_coordinates=True
            )

    _MESSAGE_MAKERS = {
        Raid: _make_raid_data.__func__,
        Spawn: _make_spawn_data.__func__,
        }

    async def close(self):
        """Close any open connections.

        :raises SenderError: on failure
        """
        try:
            self._client.close()
        except peony.exceptions.PeonyException as err:
            raise SenderError(type(err), *err.args) from err


class WebhookSender(Sender):
    """Webhook sender.
    """
    CONFIG_CLASS = notifyconfig.WebhookConfig

    # Related:
    # https://github.com/PokeAlarm/PokeAlarm/wiki/Webhook-Standard
    # https://github.com/RocketMap/RocketMap/blob/develop/docs/extras/webhooks.md

    @staticmethod
    def have_global_config():
        """Return True if this sender's global settings are configured.
        This will cause an instance to be created for the default channel.
        """
        return bool(conf.WEBHOOKS)

    def __init__(self, *, loop, websession, config=None):

        super().__init__(loop=loop, websession=websession, config=config)

        if self.config['VERIFY_TLS'] == self.websession.connector.verify_ssl:
            self._ownwebsession = False
        else:
            self._ownwebsession = True
            connector = aiohttp.TCPConnector(
                verify_ssl=self.config['VERIFY_TLS'], loop=loop)
            self.websession = aiohttp.ClientSession(
                connector=connector,
                json_serialize=json_dumps,
                read_timeout=self.config['TIMEOUT'],
                conn_timeout=self.config['TIMEOUT'],
                raise_for_status=True)

    async def _timeout_connect(self, url):
        """Connect to a webhook's server, imposing a timeout.

        :param url:         A webhook URL.
        :type  url:         str

        :raises SenderError: on timeout or connection error
        """
        try:
            request = aiohttp.ClientRequest('POST', aiohttp.client.URL(url),
                loop=self.loop)
            coro = self.websession.connector.connect(request)
            conn = await wait_for(coro, self.config['TIMEOUT'], loop=self.loop)
            conn.close()
        except asyncio.TimeoutError as err:
            raise SenderError("{} connection timed out".format(url)) from err
        except aiohttp.ClientError as err:
            raise SenderError("{} failed: {!r}".format(url, err)) from err

    async def test(self):
        """Test the ability to connect to all configured webhook servers.
        """
        await gather(*[self._timeout_connect(url)
            for url in self.config['WEBHOOKS']], loop=self.loop)

    async def send(self, event, attachments=()):
        """Send an event notification, ignoring attachments.
        """
        data = self._MESSAGE_MAKERS[type(event)](event)

        urls = self.config['WEBHOOKS']
        calls = (self._post(url, data) for url in urls)
        results = await gather(*calls, loop=self.loop, return_exceptions=True)

        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                self.log.error("Webhook {} failed: {!r}", url, result)
            else:
                self.log.debug("Webhook {} succeeded", url)

        if results and all(isinstance(r, Exception) for r in results):
            raise SenderError(*results)

    @exception_logging_coro('notifier',
        quiet=(aiohttp.ClientError, asyncio.TimeoutError))
    async def _post(self, url, data):
        """Perform an HTTP POST with a JSON-encoded dict as the body.

        :raises aiohttp.ClientError: on HTTP POST failure or error status
        :raises asyncio.TimeoutError: on timeout
        """
        async with self.websession.post(url, json=data,
            timeout=self.config['TIMEOUT']):
            pass

    @staticmethod
    def _make_raid_data(raid):
        """Return raid data suitable for posting to a webhook.
        """
        fields = {
            'gym_id':       raid['_fort'].id,
            'team_id':      raid.teamno,
            'latitude':     raid.lat,
            'longitude':    raid.lon,
            'spawn':        int(raid.spawn.timestamp()),
            'start':        int(raid.start.timestamp()),
            'end':          int(raid.end.timestamp()),
            'level':        raid.tier,
            }

        # Fields that will be present after a raid boss has hatched
        with contextlib.suppress(AttributeError):
            fields.update({
                'pokemon_id':   raid.dexno,
                'cp':           raid.cp,
                'move_1':       raid.moveno1,
                'move_2':       raid.moveno2,
                })

        return {'type': 'raid', 'message': fields}

    @staticmethod
    def _make_spawn_data(spawn):
        """Return spawn data suitable for posting to a webhook.
        """
        assert isinstance(spawn, Spawn)

        fields = {
            'encounter_id':         spawn['_wild'].encounter_id,
            'spawnpoint_id':        spawn['_wild'].spawn_point_id,
            'pokemon_id':           spawn.dexno,
            #'form':                 None, # not yet exposed by worker
            #'player_level':         None, # not yet exposed by worker
            'latitude':             spawn.lat,
            'longitude':            spawn.lon,
            'disappear_time':       round(spawn.untilmin.timestamp()),
            'last_modified_time':   spawn['_wild'].last_modified_timestamp_ms,
            'time_until_hidden_ms': spawn.remainmin * 1000,
            'seconds_until_despawn':spawn.remainmin,
            'verified':             not spawn.margin,
            #'spawn_start':          None, # not yet exposed by worker
            #'spawn_end':            None, # not yet exposed by worker
            }

        # Fields that require an encounter
        with contextlib.suppress(AttributeError):
            fields.update({
                'individual_attack':    spawn.attack,
                'individual_defense':   spawn.defense,
                'individual_stamina':   spawn.stamina,
                'move_1':               spawn.moveno1,
                'move_2':               spawn.moveno2,
                'gender':               spawn.genderno,
                'height':               spawn.height,
                'weight':               spawn.weight,
                #'cp_multiplier':        None, # not yet exposed by worker
                })

        # Fields that require an unofficial Monocle patch
        with contextlib.suppress(AttributeError):
            fields.update({
                'cp':                   spawn.cp,
                'pokemon_level':        spawn.level,
                })

        return {'type': 'pokemon', 'message': fields}

    _MESSAGE_MAKERS = {
        Raid: _make_raid_data.__func__,
        Spawn: _make_spawn_data.__func__,
        }

    async def close(self):
        """Close any open connections.

        :raises SenderError: on failure
        """
        try:
            if self._ownwebsession:
                self.websession.close()
        except aiohttp.ClientError as err:
            raise SenderError(type(err), *err.args) from err

    def __str__(self):
        return "{} {}".format(super().__str__(),
            ", ".join(self.config['WEBHOOKS']))


async def _multi_send(senders, event, attachments, *, loop, logger):
    """Send an event notification via multiple senders.

    :param senders:     Senders with which to send the notification.
    :type  senders:     Sequence[Sender]
    :param event:       Details of the event.
    :type  event:       Event
    :param attachments: Attachments to include in the notification.
    :type  attachments: Container[Attachment]
    :param loop:        An asyncio event loop.
    :type  loop:        AbstractEventLoop
    :param logger:      A logger with which to log failures.
    :type  logger:      logging.Logger
    :return:            Number of Senders that succeeded in sending.
    :rtype:             int
    """
    calls = (s.send(event, attachments) for s in senders)
    results = await gather(*calls, loop=loop, return_exceptions=True)

    for sender, result in zip(senders, results):
        if isinstance(result, KeyError) and issubclass(result.args[0], Event):
            logger.error("{} does not support {} events.",
                type(sender).__name__, type(event).__name__)
        elif isinstance(result, Exception):
            logger.error("Failed to notify {} of {}: {!r}",
                sender, event, result)
        else:
            logger.info("Notified {} of {}", sender, event)

    return len([r for r in results if not isinstance(r, Exception)])


class _Cooldown:
    """A number that drifts from a "busy" value to an "idle" value over time.
    """
    def __init__(self, *, busy=0, idle=0, duration=0):
        """Initialize cooldown value range and duration.

        :param busy:        The value to assign when reset() is called.
        :type  busy:        float
        :param idle:        The value to settle on after a cooldown period.
        :type  idle:        float
        :param duration:    The duration of the cooldown, in seconds.
        :type  duration:    float
        """
        self._busy = busy
        self._idle = idle
        self._diff = busy - idle
        self._duration = duration
        self._prior = monotonic() - duration / 2

    def reset(self):
        """Reset the cooldown to the busy value.
        """
        self._prior = monotonic()

    def get(self):
        """Return the cooldown value based on time since last reset.
        """
        if not self._diff or not self._duration:
            return self._idle

        progress = (monotonic() - self._prior) / self._duration
        if progress >= 1:
            return self._idle

        return self._busy - self._diff * progress


def _rule_to_str(rule):
    "Return a text representation of a rule."
    if isinstance(rule, bool):
        return str(rule)
    return ', '.join(str(test) for test in rule)


class Channel:
    """A group of senders and notification rules.
    """
    def __init__(self, name):
        self.name = name
        self.senders = []
        self.raidrules = {}
        self.spawnlaw = []
        self.spawnrules = {} # {pokedex-number: rule-list}
        self.cooldown = self._make_cooldown()

    def has_rules(self):
        "Return True if at least one rule is present."
        return any((self.raidrules, self.spawnlaw, self.spawnrules))

    _DEXNOS = dict((name.lower(), num) for num, name in names.POKEMON.items())

    @staticmethod
    def _make_cooldown():
        """Return a configured _Cooldown instance.
        """
        # Make cooldown values match legacy score requirements
        idleminscore = getattr(conf, 'MINIMUM_SCORE', None)
        busyminscore = getattr(conf, 'INITIAL_SCORE', idleminscore)
        if idleminscore is not None:
            if busyminscore < idleminscore:
                raise ValueError("INITIAL_SCORE must be ≥ MINIMUM_SCORE")
            return _Cooldown(busy=busyminscore, idle=idleminscore,
                duration=conf.FULL_TIME)

        return _Cooldown()

    @classmethod
    def _add_species_rule(cls, rulemap, species, rule, lineno=0):
        """Add a pokemon-specific rule to a rule map.

        :param rulemap: Map of {pokedex-number: rule-list}
        :type  rulemap: dict
        :param species: Species names or pokedex numbers to which the rules
                        will apply, or a literal ... for species that have
                        no rules of their own.
        :type  species: Container[str], Container[int], or ellipsis
        :param rule:    Either a collection of callable event tests that
                        return boolean (or raise KeyError(missing-var-name))
                        or a single boolean.  See the notifyconfig module
                        for details.
        :type  rule:    Container[Callable] or bool
        :param lineno:  Config file line number where the rule was defined,
                        or 0 if the rule did not come from the config file.
        :type  lineno:  int

        :raises ValueError: On unknown pokemon name.
        """
        if species is ...:
            species = [species]

        if not isinstance(species, Container) or isinstance(species, str):
            raise TypeError("config line {}: species must be ellipsis or "
                "a collection of pokemon names/numbers".format(lineno))
        if not isinstance(rule, (bool, Container)):
            raise TypeError("config line {}: rule must be bool or "
                "a collection of callables".format(lineno))

        for key in species:
            try:
                if isinstance(key, str):
                    key = cls._DEXNOS[key.lower()]  # look up pokemon name
            except KeyError:
                raise ValueError(
                    "config line {}: unknown pokemon {!r}".format(lineno, key))

            rulemap.setdefault(key, list()).append(rule)

    def add_raid_rule(self, species, rule, lineno=0):
        """Add a raid rule.  See _add_species_rule() for details.
        """
        return self._add_species_rule(self.raidrules, species, rule, lineno)

    def add_spawn_rule(self, species, rule, lineno=0):
        """Add a spawn rule.  See _add_species_rule() for details.
        """
        return self._add_species_rule(self.spawnrules, species, rule, lineno)

    def log_state(self, log):
        """Log internal state.
        """
        log.debug("{} state:", self)

        log.debug("  senders:")
        for sender in self.senders:
            log.debug("    {}", sender)

        if self.spawnlaw:
            log.debug("  spawn law: {}",
                ','.join(str(t) for t in self.spawnlaw))

        for kind, rulemap in [
            ('spawn', self.spawnrules), ('raid', self.raidrules)]:

            truedexnos = {dexno for dexno, rules in rulemap.items()
                if rules == [True] and dexno is not ...}
            if truedexnos:
                log.debug("  {}s always reported: {}", kind,
                    ', '.join(names.POKEMON[n] for n in sorted(truedexnos)))

            falsedexnos = {dexno for dexno, rules in rulemap.items()
                if rules == [False] and dexno is not ...}
            if falsedexnos:
                log.debug("  {}s never reported: {}", kind,
                    ', '.join(names.POKEMON[n] for n in sorted(falsedexnos)))

            otherrules = [(k, v) for k, v in rulemap.items()
                if k not in truedexnos | falsedexnos | {...}]
            for dexno, rules in sorted(otherrules):
                log.debug("  {} {} rules:", names.POKEMON[dexno], kind)
                for rule in rules:
                    log.debug("    {}", _rule_to_str(rule))

            fallbackrules = rulemap.get(..., [])
            if fallbackrules:
                log.debug("  fallback {} rules:", kind)
                for rule in fallbackrules:
                    log.debug("    {}", _rule_to_str(rule))

    def __str__(self):
        return "Channel " + (repr(self.name) if self.name else "<default>")


class ChannelMap(UserDict):  #pylint:disable=too-many-ancestors
    """A map of all configured channel names to corresponding Channel object.
    """
    def __init__(self, *, loop):
        """Initialize state from global configuration settings.

        :param loop:        An asyncio event loop.
        :type  loop:        AbstractEventLoop
        """
        super().__init__()

        self.loop = loop
        self.log = get_logger('notifier')
        self.websession = aiohttp.ClientSession(loop=loop,
            json_serialize=json_dumps,
            read_timeout=conf.NOTIFY_DEFAULT_READ_TIMEOUT,
            conn_timeout=conf.NOTIFY_DEFAULT_CONNECT_TIMEOUT,
            raise_for_status=True)

        if conf.NOTIFY:
            self._add_default_channel()
            self._add_legacy_rules()
            self._add_legacy_raid_channel()
            self._add_configured_channels()
            self._test_imports()
        elif conf.NOTIFY_RAIDS:
            self.log.warning("NOTIFY_RAIDS is deprecated and no longer works "
                "with NOTIFY disabled. Use NOTIFY and raid rules instead.")

    def _add_default_channel(self):
        """Create the default channel.
        """
        self[None] = Channel(name=None)
        for sendertype in self._SENDER_CONFIG_TYPES.values():
            if sendertype.have_global_config():
                sender = sendertype(loop=self.loop, websession=self.websession)
                self[None].senders.append(sender)

    LegacySpawnTests = namedtuple('LegacySpawnTests', 'rank score time')

    def _add_legacy_rule(self, species, tests):
        """Add LegacySpawnTests as a rule, skipping any tests that are None.
        """
        channel = self[None]
        channel.add_spawn_rule(species, [t for t in tests if t is not None])

    def _add_legacy_rules(self):
        """Populate the default channel with rules from legacy config settings.

        If conf.EMULATE_LEGACY_RARITY_BUGS is set, emulate these legacy bugs:
        - IGNORE_RARITY + time_till_hidden = no time check
          The old eligible() method skipped its TIME_REQUIRED check when
          IGNORE_RARITY was set, and the notify() method skipped its
          equivalent check if the 'time_till_hidden' key was present in the
          worker-provided pokemon details dict.  In other words, setting
          IGNORE_RARITY granted TIME_REQUIRED immunity to pokemon with known
          despawn times.
        - IGNORE_RARITY + RARITY_OVERRIDE = no rank check
          Pokemon in RARITY_OVERRIDE circumvented the requirement that they be
          in NOTIFY_RANKING or NOTIFY_IDS to be eligible, regardless of the
          override value.  The IGNORE_RARITY setting then exposed that bug
          by skipping rareness and score tests that were equivalent to the
          circumvented requirement.  In other words, using IGNORE_RARITY and
          RARITY_OVERRIDE together (even if the latter *lowered* a rareness
          value) broke the old module's promise to notify only for pokemon in
          NOTIFY_RANKING or NOTIFY_IDS.
        """
        if conf.NOTIFY_RANKING and conf.NOTIFY_IDS:
            raise ValueError("Set NOTIFY_RANKING or NOTIFY_IDS, but not both.")

        if not any((conf.NOTIFY_RANKING, conf.NOTIFY_IDS,
            conf.ALWAYS_NOTIFY_IDS)):
            # Legacy rules are not configured
            return

        channel = self[None]

        channel.add_spawn_rule(conf.NEVER_NOTIFY_IDS, False)
        channel.add_spawn_rule(conf.ALWAYS_NOTIFY_IDS, True)

        if conf.ALWAYS_NOTIFY and conf.NOTIFY_RANKING:
            channel.add_spawn_rule(...,
                [notifyconfig.rank < conf.ALWAYS_NOTIFY])

        # All rules beyond this point depend on conf.MINIMUM_SCORE
        if not hasattr(conf, 'MINIMUM_SCORE'):
            return

        if conf.IGNORE_RARITY:
            # The old notification module required that pokemon be among the
            # NOTIFY_RANKING rarest, or be in NOTIFY_IDS or ALWAYS_NOTIFY_IDS.
            # This was sometimes implemented explicitly, sometimes implicitly
            # through rareness or score tests, and sometimes not at all due to
            # a bug.  We define the rank limit here for selective use below.
            ranklimit = conf.NOTIFY_RANKING or len(
                conf.NOTIFY_IDS or conf.ALWAYS_NOTIFY_IDS) or None

            tests = self.LegacySpawnTests(
                rank=(notifyconfig.rank < ranklimit) if ranklimit else None,
                score=notifyconfig.ivfrac >= notifyconfig.cooldown,
                time=notifyconfig.remain >= conf.TIME_REQUIRED)
            self._add_legacy_rule(..., tests)

            if conf.EMULATE_LEGACY_RARITY_BUGS:
                # Legacy bug: IGNORE_RARITY + time_till_hidden = no time check
                # (We cannot directly test for the 'time_till_hidden' key since
                # our rules never see the worker-provided dict that contains it,
                # but its presence will cause our test variables to include
                # margin=0, so we test for that instead.)
                alttests = tests._replace(time=notifyconfig.margin == 0)
                self._add_legacy_rule(..., alttests)

                # Legacy bug: IGNORE_RARITY + RARITY_OVERRIDE = no rank check
                if ranklimit:
                    dexnos = conf.RARITY_OVERRIDE.keys()
                    self._add_legacy_rule(dexnos, tests._replace(rank=None))
                    self._add_legacy_rule(dexnos, alttests._replace(rank=None))

        elif conf.IGNORE_IVS:
            self._add_legacy_rule(..., self.LegacySpawnTests(
                rank=None, # Rank test is not needed; rareness test implies one
                score=notifyconfig.rareness >= notifyconfig.cooldown,
                time=notifyconfig.remain >= conf.TIME_REQUIRED))

        else:
            self._add_legacy_rule(..., self.LegacySpawnTests(
                rank=None, # Rank test is not needed; score test implies one
                score=notifyconfig.score >= notifyconfig.cooldown,
                time=notifyconfig.remain >= conf.TIME_REQUIRED))

    def _add_legacy_raid_channel(self):
        """Add channel & rules for legacy raid config settings.

        These settings were special-case ways to configure what was effectively
        a non-default notification channel.  They are deprecated in favor of
        the standard way, for consistency in configuration and code.
        """
        if not conf.NOTIFY_RAIDS:
            return

        channel = Channel(name='raid')

        if conf.TELEGRAM_RAIDS_CHAT_ID and conf.TELEGRAM_BOT_TOKEN:
            self.log.warning("TELEGRAM_RAIDS_CHAT_ID is deprecated. Configure "
                "a channel with raid rules and a Telegram sender instead.")

            tgramconfig = notifyconfig.TelegramConfig(
                CHAT_ID=conf.TELEGRAM_RAIDS_CHAT_ID)
            channel.senders.append(TelegramSender(loop=self.loop,
                websession=self.websession, config=tgramconfig))

        if conf.RAIDS_DISCORD_URL:
            self.log.warning("RAIDS_DISCORD_URL is deprecated. Configure "
                "a channel with raid rules and a Discord sender instead.")

            discordconfig = notifyconfig.DiscordConfig(
                URL=conf.RAIDS_DISCORD_URL)
            channel.senders.append(DiscordSender(loop=self.loop,
                websession=self.websession, config=discordconfig))

        if not channel.senders:
            return

        if conf.RAIDS_IDS:
            self.log.warning("RAIDS_IDS is deprecated. Use raid rules instead.")
            channel.add_raid_rule(conf.RAIDS_IDS, True)

        if conf.RAIDS_LVL_MIN:
            self.log.warning(
                "RAIDS_LVL_MIN is deprecated. Use raid rules instead.")
            channel.add_raid_rule(...,
                [notifyconfig.tier >= conf.RAIDS_LVL_MIN])

        if not channel.raidrules:
            return

        self[channel.name] = channel

    _SENDER_CONFIG_TYPES = {s.CONFIG_CLASS: s
        for s in Sender.__subclasses__()}  #pylint:disable=no-member

    def _add_configured_channels(self):
        """Create & configure named channels.

        :raises ValueError: On invalid config values.
        """
        if not isinstance(conf.NOTIFY, notifyconfig.NotifyConfig):
            return

        for channame, chanconf in conf.NOTIFY.channelconfigs.items():
            channel = self.setdefault(channame, Channel(channame))

            for species, rules, lineno in chanconf.raidargs:
                for rule in rules:
                    channel.add_raid_rule(species, rule, lineno=lineno)

            for species, rules, lineno in chanconf.spawnargs:
                if species is None:
                    channel.spawnlaw = rules[0]
                    continue
                for rule in rules:
                    channel.add_spawn_rule(species, rule, lineno=lineno)

            for senderconfig in chanconf.senderconfigs:
                sendertype = self._SENDER_CONFIG_TYPES[type(senderconfig)]
                sender = sendertype(loop=self.loop, websession=self.websession,
                    config=senderconfig)
                channel.senders.append(sender)

    def _test_imports(self):
        """Test library dependencies on all senders.

        :raises ImportError: if a sender's dependencies are missing.
        """
        if cairo:
            return

        for channel in self.values():
            if not channel.has_rules():
                continue
            for sender in channel.senders:
                if not sender.want_attachments(Spawn):
                    continue
                raise ImportError(
                    "Images are configured but cairo is not installed")

    def count_senders(self):
        """Return the total number of senders on all channels.
        """
        return len(list(itertools.chain.from_iterable(
                c.senders for c in self.values())))

    async def test_senders(self):
        """Test connectivity on all senders, logging failures.

        :return:            True if all sender tests succeed. False otherwise.
        :rtype:             bool
        """
        self.log.info("Testing senders")
        try:
            senders = list(itertools.chain.from_iterable(
                c.senders for c in self.values()))
            if not senders:
                self.log.warning("No senders are configured")
            await gather(*(s.test() for s in senders), loop=self.loop)

        except SenderError as err:
            self.log.warning("Sender test: {}", err)
            return False

        self.log.info("Tested senders")
        return True

    async def close_senders(self):
        """Close all senders, logging any exceptions.
        """
        self.log.debug("Closing senders")
        senders = list(itertools.chain.from_iterable(
            c.senders for c in self.values()))

        results = await gather(
            *(wait_for(s.close(), timeout=5, loop=self.loop) for s in senders),
            loop=self.loop, return_exceptions=True)

        for sender, result in zip(senders, results):
            if isinstance(result, Exception):
                self.log.error("Closing sender {} failed: {!r}", sender, result)

        try:
            self.websession.close()
        except aiohttp.ClientError as err:
            self.log.error("Closing shared web session failed: {!r}", err)

    def log_state(self):
        """Log internal state.
        """
        if conf.NOTIFY:
            self.log.debug("ChannelMap: conf.NOTIFY is enabled")
        self.log.debug("ChannelMap: {} channels configured:", len(self))
        for channel in self.values():
            channel.log_state(self.log)


class FortNotifier:
    """Pokestop / Gym notification manager.
    """
    def __init__(self, channelmap):
        """Initialize state from global configuration settings.

        :param channelmap:  Master channel container shared by all notifiers.
        :type  channelmap:  ChannelMap
        """
        self.loop = channelmap.loop
        self.log = get_logger('notifier')
        self._channelmap = channelmap
        self.numsent = 0

    @staticmethod
    def _make_fort_test_vars(rawfort):
        """Return variables for use by gym rules.

        :param rawfort:     FortData protobuf object.
        :type  rawfort:     FortData

        :rtype:             dict

        Variables always present:
            lat         float       Fort location latitude
            lon         float       Fort location longitude

        Variables present for gyms:
            teamno      int         Controlling team:
                                    0=neutral, 1=blue, 2=red, 3=yellow
            vacancy     int         Number of defender slots available
        """
        testvars = {}
        testvars['lat'] = rawfort.latitude
        testvars['lon'] = rawfort.longitude

        if rawfort.type == 0: # Gym
            testvars['teamno'] = rawfort.owned_by_team
            testvars['vacancy'] = rawfort.gym_display.slots_available

        return testvars

    @staticmethod
    def _make_raid_test_vars(rawraid):
        """Return supplemental variables for use by raid rules.

        :param rawraid:     RaidInfo protobuf object.
        :type  rawraid:     RaidInfo

        :rtype:             dict

        Variables always present:
            tier        int         Raid tier (1-5)
            spawn       datetime    Raid egg spawn time
            start       datetime    Raid battle start time
            end         datetime    Raid end time
            eggremain   number      Seconds until raid egg hatches
            remain      number      Seconds until raid boss leaves

        Variables present after a raid boss has hatched:
            dexno       int         Raid boss national Pokedex number
            cp          int         Combat Power
            moveno1     int         Move number
            moveno2     int         Move number
        """
        testvars = {}

        now = time()
        spawn = rawraid.raid_spawn_ms / 1000
        start = rawraid.raid_battle_ms / 1000
        end = rawraid.raid_end_ms / 1000

        testvars['tier'] = rawraid.raid_level
        testvars['spawn'] = datetime.fromtimestamp(spawn)
        testvars['start'] = datetime.fromtimestamp(start)
        testvars['end'] = datetime.fromtimestamp(end)
        testvars['eggremain'] = start - now
        testvars['remain'] = end - now

        if rawraid.HasField('raid_pokemon'):
            testvars['dexno'] = rawraid.raid_pokemon.pokemon_id
            testvars['cp'] = rawraid.raid_pokemon.cp
            testvars['moveno1'] = rawraid.raid_pokemon.move_1
            testvars['moveno2'] = rawraid.raid_pokemon.move_2

        return testvars

    @staticmethod
    def _make_fort_message_vars(fort, rawfort, testvars):
        """Return variables for use by message templates.

        :param fort:        Fort details obtained & normalized by a worker.
        :type  fort:        dict
        :param rawfort:     FortData protobuf object.
        :type  rawfort:     FortData
        :param testvars:    Variables used by tests in notification rules.
        :type  testvars:    dict

        :rtype:             dict

        Variables always present:
            fortname    str         Name
            fortdesc    str         Description
            fortimage   str         Image URL
            navurl      str         Navigation website URL
            place       str         Place / landmark name (long)
            placeshort  str         Place / landmark name (short)
            pplace      str         Place with preposition (long)
            pplaceshort str         Place with preposition (short)
            config      dict        The global configuration object
            _fort       FortData    FortData protobuf object
                                    (For internal use by this module.)

        Variables present for gyms:
            team        str         Controlling team name
        """
        msgvars = {}

        msgvars['fortname'] = fort['name']
        msgvars['fortdesc'] = fort['desc']
        msgvars['fortimage'] = fort['url']
        msgvars['navurl'] = conf.NAV_URL_FORMAT.format_map(testvars)

        if conf.LANDMARKS:
            coords = (testvars['lat'], testvars['lon'])
            landmark = conf.LANDMARKS.find_landmark(coords)
            msgvars['place'] = landmark.name
            msgvars['placeshort'] = landmark.shortname or landmark.name
            msgvars['pplace'] = landmark.generate_string(coords)
            msgvars['pplaceshort'] = landmark.generate_string(coords,
                short=True)
        else:
            msgvars['place'] = conf.AREA_NAME
            msgvars['placeshort'] = conf.AREA_NAME
            msgvars['pplace'] = msgvars['pplaceshort'] = 'in ' + conf.AREA_NAME

        if rawfort.type == 0: # Gym
            msgvars['team'] = names.TEAMS[rawfort.owned_by_team]

        msgvars['config'] = conf
        msgvars['_fort'] = rawfort

        return msgvars

    @staticmethod
    def _make_raid_message_vars(rawraid):
        """Return variables for use by message templates.

        :param rawraid:     RaidInfo protobuf object.
        :type  rawraid:     RaidInfo

        :rtype:             dict

        Variables present after a raid boss has hatched:
            name        str         Raid boss name
            move1       str         Move name
            move2       str         Move name
        """
        msgvars = {}

        if rawraid.HasField('raid_pokemon'):
            msgvars['name'] = names.POKEMON[rawraid.raid_pokemon.pokemon_id]
            msgvars['move1'] = names.MOVES[rawraid.raid_pokemon.move_1]
            msgvars['move2'] = names.MOVES[rawraid.raid_pokemon.move_2]

        return msgvars

    def _match_raid_rules(self, channel, testvars):
        """Return True if a channel wants a notification.

        :param channel:     The channel whose rules are to be checked.
        :type  channel:     Channel
        :param testvars:    Variables to be used by rule tests.
        :type  testvars:    dict
        """
        assert isinstance(channel, Channel)

        dexno = testvars.get('dexno', ...)  # Use fallback rule for raid eggs
        rules = channel.raidrules
        for rule in rules.get(dexno) or rules.get(...) or ():
            try:
                if isinstance(rule, bool):
                    return rule
                if all(test(testvars) for test in rule):
                    return True

            except KeyError as err:
                self.log.debug("{!r} from {} {} raid rule: {}",
                    err, channel, names.POKEMON[dexno], _rule_to_str(rule))
                #xxx todo: add option to notify on ambiguity?
                continue

        return False

    @exception_logging_coro('notifier', suppress=Exception)
    async def raid_notify(self, fort, rawfort):
        """Send or skip a raid notification, according to configured rules.

        :param fort:        Fort details obtained & normalized by a worker.
        :type  fort:        dict
        :param rawfort:     FortData protobuf object.
        :type  rawfort:     FortData

        :return:            True if a notification was sent.
        :rtype:             bool
        """
        # Future:  We might want to remember already-notified raids in order
        # to prevent duplicate notifications, much like SpawnNotifier does.
        # If we do that, avoiding raid_info.raid_seed as a lookup key might
        # be wise, since there have been reports of it being non-unique.

        rawraid = rawfort.raid_info
        testvars = self._make_fort_test_vars(rawfort)
        testvars.update(self._make_raid_test_vars(rawraid))

        channels = [c for c in self._channelmap.values()
            if self._match_raid_rules(c, testvars)]
        if not channels:
            return False

        msgvars = self._make_fort_message_vars(fort, rawfort, testvars)
        msgvars.update(self._make_raid_message_vars(rawraid))
        event = Raid(msgvars, testvars)

        senders = list(itertools.chain.from_iterable(
            c.senders for c in channels))

        self.log.debug("Notifying {} channels of {} raid {:04}",
            len(channels), event.get('name') or "T{}".format(event.tier),
            rawraid.raid_seed % 1000)

        count = await _multi_send(senders, event, [],
            loop=self.loop, logger=self.log)
        if count:
            self.numsent += 1
        return bool(count)


class _SpawnImager:
    """Creates images for use in pokemon spawn notifications.
    This class is just a namespace.  There is no need to instantiate it.
    """
    if conf.IMAGE_STATS and not conf.ENCOUNTER:
        raise ValueError('IMAGE_STATS is configured but ENCOUNTER is not')

    _BG_DAY = resource_string('monocle',
        'static/monocle-icons/assets/notification-bg-day.png')
    _BG_NIGHT = resource_string('monocle',
        'static/monocle-icons/assets/notification-bg-night.png')

    @classmethod
    async def create(cls, event, daytime):
        """Generate a spawn image.

        :param event:       Details of the spawn event.
        :type  event:       Spawn
        :param daytime:     Whether get_map_objects reports daytime or night.
        :type  daytime:     MapTimeOfDay, or compatible int (DAY=1, NIGHT=2).
        :return:            An image attachment.
        :rtype:             Attachment
        """
        if daytime == MapTimeOfDay.NIGHT:
            background = cls._BG_NIGHT
        else:
            background = cls._BG_DAY
        surface = cairo.ImageSurface.create_from_png(BytesIO(background))
        context = cairo.Context(surface)

        icon = await run_threaded(resource_string, 'monocle',
            'static/monocle-icons/original-icons/{}.png'.format(event.dexno))

        if conf.IMAGE_STATS:
            cls._draw_stats(context, event)
        cls._draw_image(context, icon, 224, 204)
        cls._draw_name(context, event.name, 50 if conf.IMAGE_STATS else 120)

        stream = BytesIO()
        surface.write_to_png(stream)
        return Attachment(stream.getbuffer(), 'image/png')

    @classmethod
    def _draw_stats(cls, context, event):
        """Draw a Pokemon's IVs and moves.

        :param context:     Graphics drawing context.
        :type  context:     cairo.Context
        :param event:       Details of the spawn event.
        :type  event:       Spawn
        """
        context.set_line_width(1.75)
        xpos = 240

        with contextlib.suppress(AttributeError):
            context.select_font_face(conf.IV_FONT)
            context.set_font_size(22)

            # black stroke
            cls._draw_ivs(context, xpos, event)
            context.set_source_rgba(0, 0, 0)
            context.stroke()

            # white fill
            context.move_to(xpos, 90)
            cls._draw_ivs(context, xpos, event)
            context.set_source_rgba(1, 1, 1)
            context.fill()

        if 'move1' in event or 'move2' in event:
            context.select_font_face(conf.MOVE_FONT)
            context.set_font_size(16)

            # black stroke
            cls._draw_moves(context, xpos, event)
            context.set_source_rgba(0, 0, 0)
            context.stroke()

            # white fill
            cls._draw_moves(context, xpos, event)
            context.set_source_rgba(1, 1, 1)
            context.fill()

    @staticmethod
    def _draw_ivs(context, xpos, event):
        """Draw IV text.

        :param context:     Graphics drawing context.
        :type  context:     cairo.Context
        :param xpos:        X coordinate for drawn text.
        :type  xpos:        float
        :param event:       Details of the spawn event.
        :type  event:       Spawn

        :raises AttributeError: If IVs are not in the event data.
        """
        context.move_to(xpos, 90)
        context.text_path("Attack:  {:>2}/15".format(event.attack))
        context.move_to(xpos, 116)
        context.text_path("Defense: {:>2}/15".format(event.defense))
        context.move_to(xpos, 142)
        context.text_path("Stamina: {:>2}/15".format(event.stamina))

    @staticmethod
    def _draw_moves(context, xpos, event):
        """Draw move names, if they are in the event data.

        :param context:     Graphics drawing context.
        :type  context:     cairo.Context
        :param xpos:        X coordinate for drawn text.
        :type  xpos:        float
        :param event:       Details of the spawn event.
        :type  event:       Spawn
        """
        if 'move1' in event:
            context.move_to(xpos, 170)
            context.text_path("Move 1: {}".format(event.move1))
        if 'move2' in event:
            context.move_to(xpos, 188)
            context.text_path("Move 2: {}".format(event.move2))

    @staticmethod
    def _draw_image(context, image, width, height):
        """Draw a scaled image.

        :param context:     Graphics drawing context.
        :type  context:     cairo.Context
        :param image:       Original image data in PNG format.
        :type  image:       bytes-like object
        :param width:       Desired width of the scaled image.
        :type  width:       int
        :param height:      Desired height of the scaled image.
        :type  height:      int
        """
        surface = cairo.ImageSurface.create_from_png(BytesIO(image))

        # calculate proportional scaling
        img_height = surface.get_height()
        img_width = surface.get_width()
        width_ratio = width / img_width
        height_ratio = height / img_height
        scale_xy = min(height_ratio, width_ratio)

        # scale image and add it
        context.save()
        if scale_xy < 1:
            context.scale(scale_xy, scale_xy)
            if scale_xy == width_ratio:
                new_height = img_height * scale_xy
                top = (height - new_height) / 2
                context.translate(8, top + 8)
            else:
                new_width = img_width * scale_xy
                left = (width - new_width) / 2
                context.translate(left + 8, 8)
        else:
            left = (width - img_width) / 2
            top = (height - img_height) / 2
            context.translate(left + 8, top + 8)
        context.set_source_surface(surface)
        context.paint()
        context.restore()

    @staticmethod
    def _draw_name(context, name, ypos):
        """Draw a pokemon's name.

        :param context:     Graphics drawing context.
        :type  context:     cairo.Context
        :param name:        The pokemon's name.
        :type  name:        str
        :param ypos:        Y coordinate for drawn text.
        :type  ypos:        float
        """
        xpos = 240
        context.set_line_width(2.5)
        context.select_font_face(conf.NAME_FONT)
        context.set_font_size(32)
        context.move_to(xpos, ypos)
        context.set_source_rgba(0, 0, 0)
        context.text_path(name)
        context.stroke()
        context.move_to(xpos, ypos)
        context.set_source_rgba(1, 1, 1)
        context.show_text(name)


class SpawnNotifier:
    """Spawn notification manager.
    """
    REFRESH_RANKS_SECONDS = 3600

    def __init__(self, channelmap):
        """Initialize state from global configuration settings.

        :param channelmap:  Master channel container shared by all notifiers.
        :type  channelmap:  ChannelMap
        """
        self.loop = channelmap.loop
        self.log = get_logger('notifier')

        self._channelmap = channelmap
        self._ranks = {}    #  {pokedex-number: ranking-position}
        self._rareness = {} #  {pokedex-number: rareness}

        if conf.NOTIFY:
            self._init_ranks()

        self._handled = _TempSet(loop=self.loop) # Notified encounter IDs
        self.numsent = 0

    def _init_ranks(self):
        """Load pokemon rareness values, schedule periodic updates if needed.
        """
        if conf.NOTIFY_IDS:
            # The user manually configured pokemon rank/rareness
            ranking = conf.NOTIFY_IDS
        else:
            # Automatically calculate pokemon rank/rareness from spawn data
            ranking = utils.load_pickle('ranking') or self._get_db_ranking()
            self.loop.call_later(self.REFRESH_RANKS_SECONDS,
                self._launch_refresh_ranks)

        self._ranks = self._make_rank_dict(ranking)
        self._rareness = self._make_rareness_dict(ranking)

        self.log.debug("Initial ranking for {} species: {}",
            len(self._ranks), self._ranks)
        self.log.debug("Initial rareness for {} species: {}",
            len(self._rareness), self._rareness)

    def _launch_refresh_ranks(self):
        """Create and run a _refresh_ranks() task.

        Using call_later() on this method instead of directly on
        _refresh_ranks() avoids leaving a coroutine object sitting around to
        trigger a "coroutine ... was never awaited" warning at shutdown time.
        """
        self.loop.create_task(self._refresh_ranks())

    async def _refresh_ranks(self):
        """Periodically refresh ranks & rareness using the latest database info.
        """
        try:
            ranking = await run_threaded(self._get_db_ranking, True)
            self._ranks = self._make_rank_dict(ranking)
            self._rareness = self._make_rareness_dict(ranking)
        except Exception:  #pylint:disable=broad-except
            self.log.exception("Failed to refresh pokemon ranking")

        self.log.debug("Refreshed pokemon ranking")
        # Schedule the next refresh
        self.loop.call_later(self.REFRESH_RANKS_SECONDS,
            self._launch_refresh_ranks)

    @staticmethod
    def _get_db_ranking(pickle=False):
        """Get Pokedex numbers from the database, ordered by most to least rare.
        Optionally pickle the retrieved ranking.

        Note:  This method blocks on database and filesystem access.  It is a
        @staticmethod to encourage threaded calls without unsafe access to self.

        :return:            Pokedex numbers ordered from most to least rare.
        :rtype:             Sequence

        :raises SQLAlchemyError:
        :raises PickleError:
        :raises OSError:
        :raises Exception:
        """
        with db.session_scope() as session:
            ranking = db.get_pokemon_ranking(session)

        if pickle:
            utils.dump_pickle('ranking', ranking)

        return ranking

    @staticmethod
    def _make_rank_dict(ranking):
        """Build an {item: ranking-position} dict from items ordered by rank.
        """
        return {item: pos for pos, item in enumerate(ranking)}

    @staticmethod
    def _make_rareness_dict(ranking):
        """Build an {item: rareness} dict from items ordered by rank.

        Calculate rareness values for each item in the ranking sequence,
        starting with 1.0 and decreasing with each successive item.
        The last item will have a rareness value slightly greater than 0.

        If conf.NOTIFY_RANKING is set, the input domain will be adjusted
        to include only the N highest-ranked items.  (The rest will not
        get rareness values.)  If conf.ALWAYS_NOTIFY is also set, the
        rareness range will be adjusted to assign rareness values > 1 to
        the N highest-ranked items.

        If conf.EMULATE_LEGACY_RARITY_BUGS is set, the rareness range will be
        adjusted to assign rareness values > 1 to as many of the highest-ranked
        items as there are values in conf.ALWAYS_NOTIFY_IDS.  Note that this
        only makes sense if the items in conf.ALWAYS_NOTIFY_IDS happen to be
        the highest-ranked items; the legacy behavior was buggy in other
        cases, so we preserve it only as an optional compatibility mode.

        If conf.RARITY_OVERRIDE is set, it must map items to rareness values.
        Those values will override the calculated ones.
        """
        assert len(ranking) == len(set(ranking)), "ranking contains a duplicate"

        origin = 0  # Offset within ranking sequence where rareness == 1.0

        # Let legacy config settings adjust ranking domain & rareness range
        if conf.NOTIFY_RANKING:
            ranking = ranking[:max(conf.NOTIFY_RANKING, conf.ALWAYS_NOTIFY)]
            exclude = set(ranking[:conf.ALWAYS_NOTIFY])
        else:
            exclude = set()
        if conf.EMULATE_LEGACY_RARITY_BUGS:
            # Legacy bug: Pretend ALWAYS_NOTIFY_IDS are in the rank list head
            exclude |= conf.ALWAYS_NOTIFY_IDS
        if exclude:
            origin = min(len(exclude), len(ranking))

        count = len(ranking)
        steps = max(count - origin, 1)
        rareness = {ranking[i]: 1 - (i - origin) / steps for i in range(count)}

        rareness.update(conf.RARITY_OVERRIDE)
        return rareness

    def _make_test_vars(self, pokemon):
        """Return variables for use by rules.

        Some variables will not be present in the returned dict unless
        the pokemon details include encounter data.

        :param pokemon:     Pokemon details obtained by a worker from a
                            spawn / encounter.
        :type  pokemon:     dict

        :rtype:             dict

        Variables always present:
            lat         float       Spawn location latitude
            lon         float       Spawn location longitude
            rank        Number      Position in rareness sequence: [inf, 0]
            rareness    float       Position on rareness scale: [-inf, 1.0]
            cooldown    float       Current cooldown value (configurable range)

        Variables possibly present:
            attack      int         Individual attack value
            defense     int         Individual defense value
            stamina     int         Individual stamina value
            iv          int         Individual value perfection: [0, 100]
            ivpercent   float       Individual value perfection: [0.0, 100.0]
            ivfrac      float       Individual value perfection: [0.0, 1.0]
            score       float       Arithmetic mean of ivfrac & rareness
            moveno1     int         Move number
            moveno2     int         Move number
            move1       str         Move name
            move2       str         Move name
            genderno    int         Gender: 1=male, 2=female, 3=genderless
            height      float       Height, in meters
            weight      float       Weight, in kilograms

        Additional test variables can be generated by _make_remain_vars().
        """
        # Variables based on spawn details
        testvars = {}
        testvars['lat'] = pokemon['lat']
        testvars['lon'] = pokemon['lon']
        testvars['rank'] = self._ranks.get(pokemon['pokemon_id'], float('inf'))
        testvars['rareness'] = self._rareness.get(pokemon['pokemon_id'],
            float('-inf'))

        # Variables based on encounter details, which might not be present
        with contextlib.suppress(KeyError):
            testvars['attack'] = pokemon['individual_attack']
            testvars['defense'] = pokemon['individual_defense']
            testvars['stamina'] = pokemon['individual_stamina']

            testvars['ivfrac'] = (
                pokemon['individual_attack'] +
                pokemon['individual_defense'] +
                pokemon['individual_stamina']) / 45
            testvars['ivpercent'] = testvars['ivfrac'] * 100
            testvars['iv'] = round(testvars['ivpercent'])
            testvars['score'] = (testvars['ivfrac'] + testvars['rareness']) / 2

            testvars['moveno1'] = pokemon['move_1']
            testvars['moveno2'] = pokemon['move_2']
            testvars['move1'] = names.MOVES[pokemon['move_1']]
            testvars['move2'] = names.MOVES[pokemon['move_2']]

            testvars['genderno'] = pokemon['gender']
            testvars['height'] = pokemon['height']
            testvars['weight'] = pokemon['weight']

        # Variables that require an unofficial Monocle patch
        with contextlib.suppress(KeyError):
            testvars['cp'] = pokemon['cp']
            testvars['level'] = pokemon['level']

        return testvars

    @staticmethod
    def _make_remain_vars(remainmin=None, remainmax=None):
        """Return variables for use by time-related rules.

        :param remainmin:   Minimum number of seconds until expected despawn,
                            or None to skip despawn-related variables.
        :type  remainmin:   number or None
        :param remainmax:   Maximum number of seconds until expected despawn,
                            or None to match remainmin (a precise estimate).
        :type  remainmax:   number or None

        :rtype:             dict

        Variables present if remainmin is not None:
            remainmin   number      Minimum seconds until expected despawn
            remainmax   number      Maximum seconds until expected despawn
            remain      number      Estimated seconds until despawn
            margin      number      Margin of error for estimates, in seconds
        """
        if remainmin is None:
            return {}

        if remainmax is None:
            remainmax = remainmin

        testvars = {}
        testvars['remainmin'] = remainmin
        testvars['remainmax'] = remainmax
        testvars['remain'] = (remainmax + remainmin) / 2
        testvars['margin'] = (remainmax - remainmin) / 2
        return testvars

    @staticmethod
    def _guess_time_left(pokemon):
        """Estimate a despawn time range, based on database records.
        Return a (minimum seconds remaining, maximum seconds remaining) tuple.

        Note:  This method blocks on database access.  It is a
        @staticmethod to encourage threaded calls without unsafe access to self.

        :raises SQLAlchemyError:
        """
        with db.session_scope() as session:
            return db.estimate_remaining_time(
                session, pokemon['spawn_id'], pokemon['seen'] % 3600)

    @classmethod
    async def _diligent_make_remain_vars(cls, pokemon):
        """Call _make_remain_vars() using the database to estimate missing info.
        """
        timerange = (pokemon.get('time_till_hidden'), None)

        if timerange[0] is None:
            try:
                timerange = await run_threaded(cls._guess_time_left, pokemon)

            except SQLAlchemyError:
                log = get_logger('notifier')
                log.exception("Exception while estimating despawn time")
                elapsed = time() - pokemon['seen']
                timerange = (90 - elapsed, 3600 - elapsed)

        return cls._make_remain_vars(*timerange)

    _IV_RATINGS = sorted({
        0:  "bad",
        35: "weak",
        45: "wild",
        60: "good",
        83: "great",
        99.9: "perfect",
        }.items())
    _IV_RATING_WORDS = [v for k, v in _IV_RATINGS]
    _IV_RATING_THRESHOLDS = [k for k, v in _IV_RATINGS]
    assert _IV_RATING_THRESHOLDS[0] == 0

    @classmethod
    def _make_message_vars(cls, pokemon, rawwild, testvars):
        """Return variables for use by message templates.

        :param pokemon:     Pokemon details obtained by a worker from a
                            spawn / encounter.
        :type  pokemon:     dict
        :param rawwild:     Wild pokemon protobuf object
        :type  rawwild:     WildPokemon
        :param testvars:    Variables used by tests in notification rules.
        :type  testvars:    dict

        :rtype:             dict

        Variables always present:
            name        str         Pokemon name
            dexno       int         National Pokedex number
            when        datetime    Date & time when spawn was detected
            until       datetime    Estimated despawn date & time
            untilmin    datetime    Earliest expected despawn time
            untilmax    datetime    Latest expected despawn time
            remainrange str         Remaining duration: DURATION_RANGE_FORMAT
            untilrange  str         Despawn time: TIME_RANGE_FORMAT
            rating      str         Description of pokemon quality
            hashtags    Set[str]    Hashtag names
            navurl      str         Navigation website URL
            place       str         Place / landmark name (long)
            placeshort  str         Place / landmark name (short)
            pplace      str         Place with preposition (long)
            pplaceshort str         Place with preposition (short)
            config      dict        The global configuration object
            _wild       WildPokemon Wild pokemon protobuf object.
                                    (For internal use by this module.)

        Variables possibly present:
            gender      str         Gender: "♂", "♀", "⚲"
            gendertext  str         Gender: 'male, 'female, 'genderless'
        """
        msgvars = {}
        msgvars['name'] = names.POKEMON[pokemon['pokemon_id']]
        msgvars['dexno'] = pokemon['pokemon_id']

        if conf.TZ_OFFSET:
            zone = timezone(timedelta(hours=conf.TZ_OFFSET))
        else:
            zone = None
        when = datetime.fromtimestamp(pokemon['seen'], zone)
        msgvars['when'] = when
        msgvars['until'] = when + timedelta(seconds=testvars['remain'])
        msgvars['untilmin'] = when + timedelta(seconds=testvars['remainmin'])
        msgvars['untilmax'] = when + timedelta(seconds=testvars['remainmax'])

        formatter = _EventFormatter()
        if testvars['margin']:
            msgvars['remainrange'] = formatter.format(
                conf.DURATION_RANGE_FORMAT,
                min=timedelta(seconds=testvars['remainmin']),
                mid=timedelta(seconds=testvars['remain']),
                max=timedelta(seconds=testvars['remainmax']),
                margin=timedelta(seconds=testvars['margin']))
            msgvars['untilrange'] = formatter.format(
                conf.DATETIME_RANGE_FORMAT,
                min=msgvars['untilmin'],
                mid=msgvars['until'],
                max=msgvars['untilmax'],
                margin=timedelta(seconds=testvars['margin']))
        else:
            msgvars['remainrange'] = formatter.format_field(
                timedelta(seconds=testvars['remain']))
            msgvars['untilrange'] = formatter.format_field(msgvars['until'])

        ivpercent = testvars.get('ivpercent')
        if ivpercent is None:
            msgvars['rating'] = "wild"
        else:
            index = bisect.bisect(cls._IV_RATING_THRESHOLDS, ivpercent) - 1
            msgvars['rating'] = cls._IV_RATING_WORDS[index]

        msgvars['hashtags'] = _HashTagSet(conf.HASHTAGS or ())
        msgvars['navurl'] = conf.NAV_URL_FORMAT.format_map(testvars)

        if conf.LANDMARKS:
            coords = (testvars['lat'], testvars['lon'])
            landmark = conf.LANDMARKS.find_landmark(coords)
            msgvars['place'] = landmark.name
            msgvars['placeshort'] = landmark.shortname or landmark.name
            msgvars['pplace'] = landmark.generate_string(coords)
            msgvars['pplaceshort'] = landmark.generate_string(coords,
                short=True)
            if landmark.hashtags:
                msgvars['hashtags'].update(landmark.hashtags)
        else:
            msgvars['place'] = conf.AREA_NAME
            msgvars['placeshort'] = conf.AREA_NAME
            msgvars['pplace'] = msgvars['pplaceshort'] = 'in ' + conf.AREA_NAME

        with contextlib.suppress(KeyError):
            msgvars['gender'] = conf.GENDER_SYMBOLS[testvars['genderno']]
            msgvars['gendertext'] = conf.GENDER_TEXT[testvars['genderno']]

        msgvars['config'] = conf
        msgvars['_wild'] = rawwild

        return msgvars

    def _match_rules(self, channel, dexno, testvars, optimism=False):
        """Return True if a channel wants a spawn notification.

        :param channel:     The channel whose spawn rules are to be checked.
        :type  channel:     Channel
        :param dexno:       National Pokedex number
        :type  dexno:       int
        :param testvars:    Variables to be used by rule tests.
        :type  testvars:    dict
        :param optimism:    Whether to assume missing variables satisfy tests.
        :type  optimism:    bool
        """
        assert isinstance(channel, Channel)

        testvars = ChainMap(testvars, {'cooldown': channel.cooldown.get()})

        if optimism:
            def run_test(test):
                "Run a test with optimistic KeyError handling."
                try:
                    return test(testvars)
                except KeyError as err:
                    if not conf.ENCOUNTER:
                        #xxx todo: add option to notify on ambiguity?
                        return False  # Test will always fail without encounter
                    if err.args[0] == 'score':
                        # Retry the test with simulated max & min score values
                        rareness = testvars['rareness']
                        return any(test(testvars.new_child({'score': s}))
                            for s in ((rareness + 1) / 2, rareness / 2))
                    return True
        else:
            def run_test(test):
                "Run a test without catching KeyError."
                return test(testvars)

        if not all(run_test(test) for test in channel.spawnlaw):
            return False

        rules = channel.spawnrules
        for rule in rules.get(dexno) or rules.get(...) or ():
            try:
                if isinstance(rule, bool):
                    return rule
                if all(run_test(test) for test in rule):
                    return True

            except KeyError as err:
                self.log.debug("{!r} from {} {} spawn rule: {}",
                    err, channel, names.POKEMON[dexno], _rule_to_str(rule))
                #xxx todo: add option to notify on ambiguity?
                continue

        return False

    def eligible(self, pokemon):
        """Return True if a spawn could potentially trigger a notification.

        This runs a preliminary rule check that is tolerant of missing
        pokemon details, so workers can quickly decide whether to bother with
        slow detail-gathering operations like an encounter.  If this method
        returns False, no further notification processing is necessary.

        :param pokemon:     Pokemon spawn details, possibly without encounter
                            details.
        :type  pokemon:     dict
        """
        dexno = pokemon['pokemon_id']
        if pokemon['encounter_id'] in self._handled:
            return False

        testvars = self._make_test_vars(pokemon)
        testvars.update(self._make_remain_vars(pokemon.get('time_till_hidden')))

        result = any(self._match_rules(channel, dexno, testvars, optimism=True)
            for channel in self._channelmap.values())

        return result

    @exception_logging_coro('notifier', suppress=Exception)
    async def notify(self, pokemon, rawwild, daytime):
        """Send or skip a spawn notification, according to configured rules.

        :param pokemon:     Pokemon spawn / encounter details.
        :type  pokemon:     dict
        :param rawwild:     Wild pokemon protobuf object
        :type  rawwild:     WildPokemon
        :param daytime:     Whether get_map_objects reports daytime or night.
        :type  daytime:     MapTimeOfDay, or compatible int (DAY=1, NIGHT=2).

        :return:            True if a notification was sent.
        :rtype:             bool
        """
        dexno = pokemon['pokemon_id']
        encounter_id = pokemon['encounter_id']

        if encounter_id in self._handled:
            self.log.debug("Already notified: {}.{}",
                names.POKEMON[dexno], encounter_id % 1000)
            return False

        with self._handled.temp_add(encounter_id) as handling:

            testvars = self._make_test_vars(pokemon)
            testvars.update(await self._diligent_make_remain_vars(pokemon))

            #xxx todo: pass optimism=True if configured to notify on ambiguity?
            channels = [c for c in self._channelmap.values()
                if self._match_rules(c, dexno, testvars)]
            if not channels:
                return False

            msgvars = self._make_message_vars(pokemon, rawwild, testvars)
            event = Spawn(msgvars, testvars)

            for channel in channels:
                channel.cooldown.reset()

            senders = list(itertools.chain.from_iterable(
                c.senders for c in channels))
            if any(s.want_attachments(Spawn) for s in senders):
                attachments = [await _SpawnImager.create(event, daytime)]
            else:
                attachments = []

            self.log.debug("Notifying {} channels of spawn: {}.{}",
                len(channels), names.POKEMON[dexno], encounter_id % 1000)

            count = await _multi_send(senders, event, attachments,
                loop=self.loop, logger=self.log)
            if count:
                self.numsent += 1
                handling.keep(testvars.get('remainmax', 3600))
            return bool(count)


class Notifier:
    """Master notification manager. Wraps event-type-specific notifiers.
    """
    def __init__(self, *, loop):
        """Initialize all event notifier classes.

        :param loop:        An asyncio event loop.
        :type  loop:        AbstractEventLoop
        """
        self._channelmap = ChannelMap(loop=loop)
        self._fortnotifier = FortNotifier(self._channelmap)
        self._spawnnotifier = SpawnNotifier(self._channelmap)

    def count_senders(self):
        """Return the total number of senders on all channels.
        """
        return self._channelmap.count_senders()

    async def test_senders(self):
        """Call the ChannelMap's test_senders() method.
        """
        return await self._channelmap.test_senders()

    async def close_senders(self):
        """Call the ChannelMap's close_senders() method.
        """
        return await self._channelmap.close_senders()

    def log_state(self):
        """Log internal state.
        """
        self._channelmap.log_state()

    async def raid_notify(self, fort, rawfort):
        """Send or skip a raid notification, according to configured rules.
        See FortNotifier.raid_notify() method for details.
        """
        return await self._fortnotifier.raid_notify(fort, rawfort)

    def spawn_eligible(self, pokemon):
        """Return True if a spawn could potentially trigger a notification.
        See SpawnNotifier.eligible() method for details.
        """
        return self._spawnnotifier.eligible(pokemon)

    async def spawn_notify(self, pokemon, rawwild, daytime):
        """Send or skip a spawn notification, according to configured rules.
        See SpawnNotifier.notify() method for details.
        """
        return await self._spawnnotifier.notify(pokemon, rawwild, daytime)

    def get_sent_count(self):
        """Get the number of events for which notifications have been sent.
        """
        return self._fortnotifier.numsent + self._spawnnotifier.numsent
