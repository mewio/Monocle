"""
DO NOT ATTEMPT TO CONFIGURE MONOCLE BY EDITING THIS FILE.

All configuration settings belong in config.py.  This module contains helpers
for importing into config.py.  See examples below, or in config.example.py.


Senders
-------

Notifications are delivered via senders, each of which can deliver to
recipients on a single messaging service (e.g. Twitter or SMTP).  When a
Monocle instance will always be sending notifications to the same recipients,
global config variables are sufficient to configure the senders.
Config file example:

    SMTP_HOST = 'mail.example.com'
    SMTP_TO = ['myself@example.net', 'myfriend@example.net']


Channels
--------

It is also possible to create multiple notification channels, each with
its own recipients, using the NotifyConfig and sender configuration
classes (SMTPConfig, etc).  Config file example:

    from .notifyconfig import *
    NOTIFY = NotifyConfig()

    SMTP_HOST = 'mail.example.com'

    NOTIFY.senders(
        SMTPConfig(TO=['alice@example.org', 'bob@example.org']),
        PushbulletConfig(API_KEY='abc', CHANNEL=123),
        channel='friends')

    NOTIFY.senders(SMTPConfig(TO=['joe@example.org']), channel='joe')

Monocle automatically creates a default channel with senders configured by
global variables like SMTP_FROM & SMTP_TO.  Additional channels are created
and configured whenever one is named in a NotifyConfig method call, as shown
above.

Sender configuration classses are available for each messaging service, and
are used to configure channel-specific senders.  They are instantiated like
dicts, with keys corresponding to similarly-named global config variables.
If one of these keys are omitted, the corresponding global config variable
will be used instead.


Rules
-----

When an event (like a pokemon spawn) occurs, Monocle consults rules
to decide whether to send a notification.

A rule is usually written as a bunch of python expressions, using helper
objects named after event variables, like this:  [attack >= 14, stamina >= 9]
Internally, each expression evaluates to a single-argument callable "test" that
accepts a dict of event variables and returns a boolean indicating whether the
test passed, or else raises KeyError(variable-name) if a required event
variable is missing.  A rule will pass if and only if all of its tests return
true (logical AND).

Alternatively, a rule can be a single boolean value, meaning that the rule will
always pass or always fail.

A notification will be sent if any rule passes (logical OR).

The NotifyConfig class provides methods for configuring rules on either
the default channel or a named channel.  Config file example:

    from .notifyconfig import *
    NOTIFY = NotifyConfig()

    # One rule on the default channel:  must have iv > 80 and level >= 20
    NOTIFY.spawn(['dratini', 'dragonair'], [iv > 80, level >= 20])

    # Two rules on a named channel:  must have iv > 95 or attack == 15
    NOTIFY.spawn(['machop'], [iv > 95], [attack == 15], channel='chops')

    # One rule on a named channel:  always notify for pokedex number 201
    NOTIFY.spawn([201], True, channel='unowns')

Most spawn rules apply to specific pokemon species, but fallback rules can
also be defined by passing the python Ellipsis object (...) in place of a
species list.  These rules will apply to any species that have no rules
of their own:

    NOTIFY.spawn(..., [rareness > 0.7])

In addition to rules, any channel can have a spawn "law": a bunch of tests that
must always pass in order to be eligible for notification.  Defining a law is
functionally the same as adding the same test(s) to every rule, but simpler
to read and write.  For example:

    NOTIFY.spawn_law(remain > 600)

Raid rules are configured similarly to spawn rules:

    NOTIFY.raid('tyranitar', True)
    NOTIFY.raid(..., [tier >= 4])
    NOTIFY.raid(..., [tier < 4], channel='solo')


"""

from collections import namedtuple, UserDict
import inspect
import operator


#pylint:disable=too-many-ancestors


class SenderConfig(UserDict):
    """Base class for sender configuration containers.
    """
    KEYS = dict()  # {config-key: equivalent-global-config-key}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in self.keys():
            if not key in self.KEYS:
                raise TypeError("{!r} is not a {} setting".format(
                    key, self.__class__.__name__))


class DiscordConfig(SenderConfig):
    """Discord sender configuration container.
    """
    KEYS = dict(
        URL='DISCORD_URL',
        )


class PushbulletConfig(SenderConfig):
    """Pushbullet sender configuration container.
    """
    KEYS = dict(
        API_KEY='PUSHBULLET_API_KEY',
        CHANNEL='PUSHBULLET_CHANNEL',
        )


class SMTPConfig(SenderConfig):
    """SMTP sender configuration container.
    """
    KEYS = dict(
        HOST='SMTP_HOST',
        PORT='SMTP_PORT',
        TLS='SMTP_TLS',
        STARTTLS='SMTP_STARTTLS',
        TIMEOUT='SMTP_TIMEOUT',
        USERNAME='SMTP_USERNAME',
        PASSWORD='SMTP_PASSWORD',
        FROM='SMTP_FROM',
        TO='SMTP_TO',
        ATTACH='SMTP_ATTACH',
        )


class TelegramConfig(SenderConfig):
    """Telegram sender configuration container.
    """
    KEYS = dict(
        BOT_TOKEN='TELEGRAM_BOT_TOKEN',
        CHAT_ID='TELEGRAM_CHAT_ID',
        )


class TwitterConfig(SenderConfig):
    """Twitter sender configuration container.
    """
    KEYS = dict(
        ACCESS_KEY='TWITTER_ACCESS_KEY',
        ACCESS_SECRET='TWITTER_ACCESS_SECRET',
        CONSUMER_KEY='TWITTER_CONSUMER_KEY',
        CONSUMER_SECRET='TWITTER_CONSUMER_SECRET',
        IMAGES='TWEET_IMAGES',
        )


class WebhookConfig(SenderConfig):
    """Webhook sender configuration container.
    """
    KEYS = dict(
        TIMEOUT='WEBHOOK_TIMEOUT',
        VERIFY_TLS='WEBHOOK_VERIFY_TLS',
        WEBHOOKS='WEBHOOKS',
        )


_RuleArgs = namedtuple('_RuleArgs', 'species rules lineno')


class _ChannelConfig:
    """Container for a single channel configuration.
    """
    def __init__(self):
        self.senderconfigs = [] # SenderConfig instances
        self.raidargs = []      # _RuleArgs instances
        self.spawnargs = []     # _RuleArgs instances


class NotifyConfig:
    """Channel configuration container, for use as the NOTIFY config setting.
    """
    def __init__(self):
        self.channelconfigs = {}
        self.enabled = True

    def __bool__(self):
        # Legacy config files used NOTIFY = True or False, while modern ones
        # use NOTIFY = NotifyConfig().  This method simplifies checking both.
        return self.enabled

    def enable(self, enabled=True):
        """Enable or disable notifications.
        """
        self.enabled = enabled

    def senders(self, *senders, channel=None):
        """Configure a channel's senders.

        :param senders: One or more sender configurations.
        :type senders:  Container[SenderConfig]
        :param channel: The channel name.
        :type channel:  str or None
        """
        if not all(isinstance(s, SenderConfig) for s in senders):
            raise TypeError("senders must be SenderConfig subclass instances")

        chanconf = self.channelconfigs.setdefault(channel, _ChannelConfig())
        chanconf.senderconfigs.extend(senders)

    def raid(self, species, *rules, channel=None):
        """Add to a channel's raid rules.

        :param species: Species names or pokedex numbers to which the rules
                        will apply, or a literal ... for species that have
                        no rules of their own.
        :type species:  Container[str], Container[int], or ellipsis
        :param rules:   Zero or more rules.

                        A rule is usually written as a bunch of python
                        expressions, using helper objects named after event
                        variables, like this:  [attack >= 14, stamina >= 9]
                        Internally, each expression evaluates to a
                        single-argument callable "test" that accepts a dict of
                        event variables and returns a boolean indicating
                        whether the test passed, or else raises
                        KeyError(variable-name) if a required event variable is
                        missing.  A rule will pass if and only if all of its
                        tests return true (logical AND).

                        Alternatively, a rule can be a single boolean value,
                        meaning that the rule will always pass or always fail.

                        If no rules are given, a single True rule (always pass)
                        is added for the given species.

                        A notification will be sent if any rule passes
                        (logical OR).
        :type rules:    Container[Container[Callable] or bool]
        :param channel: The channel name.
        :type channel:  str or None
        """
        if not species or isinstance(species, (str, int)):
            raise TypeError("first arg must be ... or a collection of species")

        if not rules:
            rules = [True]

        # Resolving species names here is impractical because the names module
        # (as of 2017) requires the config to be fully loaded, but this method
        # is called while that module is still loading.  We therefore store our
        # arguments (along with the calling line number from the config file)
        # and let the notifier module process them later.

        lineno = inspect.stack()[1].lineno
        chanconf = self.channelconfigs.setdefault(channel, _ChannelConfig())
        chanconf.raidargs.append(_RuleArgs(species, rules, lineno))

    def spawn(self, species, *rules, channel=None):
        """Add to a channel's spawn rules.
        See the raid() method for details.
        """
        if not species or isinstance(species, (str, int)):
            raise TypeError("first arg must be ... or a collection of species")

        if not rules:
            rules = [True]

        lineno = inspect.stack()[1].lineno
        chanconf = self.channelconfigs.setdefault(channel, _ChannelConfig())
        chanconf.spawnargs.append(_RuleArgs(species, rules, lineno))

    def spawn_law(self, *tests, channel=None):
        """Set a channel's spawn law.  (Each call overrides previous ones.)

        :param tests:   One or more event variable tests that must pass
                        in order for a notification to be sent.  The same
                        helper objects and expressions used in rules can be
                        used here.  This is a convenient way to define in one
                        place tests that would otherwise be repeated in all
                        rules for all species.
        :type tests:    Container[Callable]
        :param channel: The channel name.
        :type channel:  str or None
        """
        if not all(callable(t) for t in tests):
            raise TypeError("laws must be callable tests")

        lineno = inspect.stack()[1].lineno
        chanconf = self.channelconfigs.setdefault(channel, _ChannelConfig())
        chanconf.spawnargs.append(_RuleArgs(None, [tests], lineno))


class _GetOper:
    """A callable that wraps operator and operands (which can be value-getters).

    When called, an instance assumes its argument is a mapping, resolves
    wrapped value-getters into values by calling them on that mapping, and
    passes stored & resolved values as arguments to the wrapped function.

    This is something like functools.partial(), except:
    - Arguments to the wrapped function can be either specified at init time
      or looked up by value-getters at call time.
    - No arguments to the wrapped function are accepted at call time.
      A single mapping argument (for use by value-getters) takes their place.
    - It is specifically for wrapping an operator-like binary function,
      including conveniences like a string representation for pretty printing.

    Example:

        >>> import operator
        >>> match123 = _GetOper('==', operator.eq, _Getter('someval'), 123)
        >>> smallvars = {'someval': 1}
        >>> bigvars = {'someval': 123}
        >>> match123(smallvars)
        False
        >>> match123(bigvars)
        True
        >>> print(match123)
        (someval == 123)

    Instances of this class are useful as notification rule tests.
    """
    def __init__(self, opstr, opfunc, left, right):
        assert isinstance(left, _Getter) or isinstance(right, _Getter)
        self.opstr = opstr
        self.opfunc = opfunc
        self.left = left
        self.right = right

    def __call__(self, fields):
        if isinstance(self.left, _Getter):
            leftval = self.left(fields)
        else:
            leftval = self.left
        if isinstance(self.right, _Getter):
            rightval = self.right(fields)
        else:
            rightval = self.right
        return self.opfunc(leftval, rightval)

    def __bool__(self):
        raise TypeError("{} for {} must be called to produce a bool".format(
            self.__class__.__name__, self))

    def __str__(self):
        return "{} {} {}".format(self.left, self.opstr, self.right)

    def __repr__(self):
        return "{}({!r}, {!r}, {!r}, {!r})".format(self.__class__.__name__,
            self.opstr, self.opfunc, self.left, self.right)


class _Getter:
    """Represent / get a value from an external mapping.
    """
    def __init__(self, key):
        self.key = key

    def __call__(self, fields):
        return fields[self.key]

    def __bool__(self):
        raise TypeError("{!r} must be called to produce a bool".format(self))

    def __hash__(self):
        raise TypeError("{!r} cannot belong to a set or dict".format(self))

    def __str__(self):
        return "{}".format(self.key)

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, self.key)

    #pylint:disable=bad-whitespace,multiple-statements
    def __lt__(self, other): return _GetOper('<',  operator.lt, self, other)
    def __le__(self, other): return _GetOper('<=', operator.le, self, other)
    def __eq__(self, other): return _GetOper('==', operator.eq, self, other)
    def __ne__(self, other): return _GetOper('!=', operator.ne, self, other)
    def __gt__(self, other): return _GetOper('>',  operator.gt, self, other)
    def __ge__(self, other): return _GetOper('>=', operator.ge, self, other)

    def __and__(self, other): return _GetOper('&', operator.and_, self, other)
    def __xor__(self, other): return _GetOper('^', operator.xor,  self, other)
    def __or__(self, other):  return _GetOper('|', operator.or_,  self, other)


# Event variable getters
#pylint:disable=bad-whitespace,invalid-name

lat =       _Getter('lat')
lon =       _Getter('lon')
remainmin = _Getter('remainmin')
remainmax = _Getter('remainmax')
remain =    _Getter('remain')
margin =    _Getter('margin')
cp =        _Getter('cp')
level =     _Getter('level')
attack =    _Getter('attack')
defense =   _Getter('defense')
stamina =   _Getter('stamina')
cooldown =  _Getter('cooldown')
rank =      _Getter('rank')
rareness =  _Getter('rareness')
iv =        _Getter('iv')
ivpercent = _Getter('ivpercent')
ivfrac =    _Getter('ivfrac')
score =     _Getter('score')
height =    _Getter('height')
weight =    _Getter('weight')
tier =      _Getter('tier')
