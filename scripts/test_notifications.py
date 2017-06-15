#!/usr/bin/env python3

from asyncio import get_event_loop, set_event_loop_policy
from pathlib import Path
from cyrandom import uniform, randint, choice
from argparse import ArgumentParser

try:
    from uvloop import EventLoopPolicy
    set_event_loop_policy(EventLoopPolicy())
except ImportError:
    pass

import time
import logging
import sys

monocle_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(monocle_dir))

from monocle import names, notifyconfig, sanitized as conf

parser = ArgumentParser()
parser.add_argument(
    '-i', '--id',
    type=int,
    help='Pokémon ID to notify about'
)
parser.add_argument(
    '-lat', '--latitude',
    type=float,
    help='latitude for fake spawn'
)
parser.add_argument(
    '-lon', '--longitude',
    type=float,
    help='longitude for fake spawn'
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
args = parser.parse_args()

if args.id is not None:
    pokemon_id = args.id
    if args.id == 0:
        names.POKEMON[0] = 'Test'
else:
    pokemon_id = randint(1, 387)

if not args.unmodified:
    conf.ALWAYS_NOTIFY_IDS = {pokemon_id}
    conf.NEVER_NOTIFY_IDS = {}
    if isinstance(conf.NOTIFY, notifyconfig.NotifyConfig):
        conf.NOTIFY.spawn_law()  # Avoid config file interference

conf.HASHTAGS = {'test'}

from monocle.notifier import Notifier
from monocle.names import MOVES

root = logging.getLogger()
root.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
root.addHandler(ch)

MOVES = tuple(MOVES.keys())

if args.latitude is not None:
    lat = args.latitude
else:
    lat = uniform(conf.MAP_START[0], conf.MAP_END[0])

if args.longitude is not None:
    lon = args.longitude
else:
    lon = uniform(conf.MAP_START[1], conf.MAP_END[1])

if args.remaining:
    tth = args.remaining
else:
    tth = uniform(89, 3599)

now = time.time()

pokemon = {
    'encounter_id': 93253523,
    'spawn_id': 3502935,
    'pokemon_id': pokemon_id,
    'time_till_hidden': tth,
    'lat': lat,
    'lon': lon,
    'individual_attack': randint(0, 15),
    'individual_defense': randint(0, 15),
    'individual_stamina': randint(0, 15),
    'seen': now,
    'move_1': choice(MOVES),
    'move_2': choice(MOVES),
    'gender': randint(1, 3),
    'height': uniform(0.3, 4.0),
    'weight': uniform(1, 600),
    'valid': True,
    'expire_timestamp': now + tth
}

loop = get_event_loop()
notifier = Notifier(loop=loop)
notifier.log_state()

#if not loop.run_until_complete(notifier.test_senders()):
#    sys.exit(1)

if loop.run_until_complete(notifier.spawn_notify(pokemon, randint(1, 2))):
    print('Success')
else:
    print('Failure')
loop.run_until_complete(notifier.close_senders())

loop.close()
