#!/usr/bin/env python3

"""
Notification test utility.
"""

import argparse
from asyncio import get_event_loop, set_event_loop_policy
import logging
from pathlib import Path
import sys
import time

from aiopogo.pogoprotos.map.pokemon.wild_pokemon_pb2 import WildPokemon
from aiopogo.pogoprotos.map.fort.fort_data_pb2 import FortData
from aiopogo.pogoprotos.map.fort.fort_type_pb2 import GYM
from cyrandom import uniform, randint, choice
try:
    import uvloop
except ImportError:
    uvloop = None

MONOCLE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(MONOCLE_DIR))
#pylint:disable=wrong-import-position
import monocle.names
import monocle.notifier
from monocle import notifyconfig, sanitized as conf


MOVE_NUMBERS = tuple(monocle.names.MOVES.keys())


def parse_command_line():
    """Parse command line options.
    """
    loglevels = ['debug', 'info', 'warning', 'error', 'critical']

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-e', '--event',
        default='spawn',
        choices=('raid', 'raidegg', 'spawn'),
        help="event type to simulate"
    )
    parser.add_argument(
        '-d', '--dexno',
        type=int,
        help='pokédex number for fake event'
    )
    parser.add_argument(
        '-lat', '--latitude',
        type=float,
        help='latitude for fake event'
    )
    parser.add_argument(
        '-lon', '--longitude',
        type=float,
        help='longitude for fake event'
    )
    parser.add_argument(
        '-r', '--remaining',
        type=int,
        help='seconds remaining on fake spawn'
    )
    parser.add_argument(
        '-u', '--unmodified',
        action='store_true',
        help="don't modify ALWAYS_NOTIFY_IDS / NEVER_NOTIFY_IDS"
    )
    parser.add_argument(
        '-t', '--test',
        action='store_true',
        help="test senders before attempting to send a notification"
    )
    parser.add_argument(
        '--log-level',
        default='WARNING',
        choices=loglevels,
        help='set log level'
    )

    options = parser.parse_args()

    if options.dexno is None:
        options.dexno = randint(1, 387)

    if options.latitude is None:
        options.latitude = uniform(conf.MAP_START[0], conf.MAP_END[0])

    if options.longitude is None:
        options.longitude = uniform(conf.MAP_START[1], conf.MAP_END[1])

    if options.remaining is None:
        options.remaining = randint(89, 3599)

    return options


def configure_logger(options):
    """Initialize logging.
    """
    level = options.log_level.upper()
    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    root.addHandler(handler)


def monkey_patch_modules(options):
    """Monkey patch imported modules, so we can cheat a bit.
    """
    if options.dexno == 0:
        monocle.names.POKEMON[0] = "Test Pokemon"

    if not options.unmodified:
        # Keep config file settings from blocking notifications
        conf.ALWAYS_NOTIFY_IDS = {options.dexno}
        conf.NEVER_NOTIFY_IDS = {}
        if isinstance(conf.NOTIFY, notifyconfig.NotifyConfig):
            conf.NOTIFY.spawn_law()

    conf.HASHTAGS = {'test'}


async def test_raid(notifier, options):
    """Generate a notification for a fake pokemon spawn.
    """
    now_ms = int(time.time() * 1000)

    rawfort = FortData(
        id="ABCXYZ",
        latitude=options.latitude,
        longitude=options.longitude,
        owned_by_team=randint(0, 3),
        type=GYM,
        )
    rawfort.gym_display.slots_available = randint(0, 5)

    rawfort.raid_info.raid_spawn_ms = now_ms
    rawfort.raid_info.raid_battle_ms = now_ms + options.remaining * 500
    rawfort.raid_info.raid_end_ms = now_ms + options.remaining * 1000
    rawfort.raid_info.raid_level = randint(1, 5)

    if options.event == 'raid':
        rawfort.raid_info.raid_pokemon.pokemon_id = options.dexno
        rawfort.raid_info.raid_pokemon.cp = randint(10, 2844)
        rawfort.raid_info.raid_pokemon.move_1 = choice(MOVE_NUMBERS)
        rawfort.raid_info.raid_pokemon.move_2 = choice(MOVE_NUMBERS)

    normalfort = dict(
        name="Some Random Gym",
        desc="A gym that does not actually exist.",
        url="https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg",
        )

    return await notifier.raid_notify(normalfort, rawfort)


async def test_spawn(notifier, options):
    """Generate a notification for a fake pokemon spawn.
    """
    remain_ms = options.remaining * 1000
    now_ms = int(time.time() * 1000)

    rawwild = WildPokemon(
        encounter_id=93253523,
        last_modified_timestamp_ms=now_ms,
        latitude=options.latitude,
        longitude=options.longitude,
        spawn_point_id='58eef93',
        time_till_hidden_ms=remain_ms,
        )

    if conf.SPAWN_ID_INT:
        spawnpt_id = int(rawwild.spawn_point_id, 16)
    else:
        spawnpt_id = rawwild.spawn_point_id,

    normalmon = {
        'encounter_id': rawwild.encounter_id,
        'spawn_id': spawnpt_id,
        'pokemon_id': options.dexno,
        'time_till_hidden': remain_ms // 1000,
        'lat': options.latitude,
        'lon': options.longitude,
        'individual_attack': randint(0, 15),
        'individual_defense': randint(0, 15),
        'individual_stamina': randint(0, 15),
        'seen': now_ms // 1000,
        'move_1': choice(MOVE_NUMBERS),
        'move_2': choice(MOVE_NUMBERS),
        'gender': randint(1, 3),
        'height': uniform(0.3, 4.0),
        'weight': uniform(1, 600),
        'valid': True,
        'expire_timestamp': (now_ms + remain_ms) // 1000
        }

    return await notifier.spawn_notify(normalmon, rawwild, randint(1, 2))


def main():
    """Program entry point.
    """
    options = parse_command_line()
    configure_logger(options)
    monkey_patch_modules(options)


    if conf.UVLOOP and uvloop:
        set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = get_event_loop()
    notifier = monocle.notifier.Notifier(loop=loop)
    notifier.log_state()

    if options.test:
        if not loop.run_until_complete(notifier.test_senders()):
            sys.exit(1)

    if options.event in {'raid', 'raidegg'}:
        coro = test_raid(notifier, options)
    else:
        coro = test_spawn(notifier, options)
    result = loop.run_until_complete(coro)

    if result:
        print("Notification was sent.")
    elif not conf.NOTIFY:
        print("Cannot notify because notifications are disabled.")
    elif not notifier.count_senders():
        print("Cannot notify because no senders are configured.")
    else:
        print("Notification was not sent.")

    loop.run_until_complete(notifier.close_senders())
    loop.close()


if __name__ == '__main__':
    main()
