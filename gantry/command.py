from __future__ import print_function, unicode_literals

from argh import arg, ArghParser
import logging

from .gantry import Gantry, GantryError, DOCKER_DEFAULT_URL

_log_level_default = logging.WARN
_log_level = getattr(logging, env.get('GANTRY_LOGLEVEL', '').upper(), _log_level_default)
logging.basicConfig(format='%(levelname)s: %(message)s', level=_log_level)


@arg('-f', '--from-tag', required=True)
@arg('-t', '--to-tag', required=True)
@arg('repository')
def deploy(args):
    gantry = Gantry(args.base_url)
    try:
        gantry.deploy(args.repository, args.to_tag, args.from_tag)
    except GantryError as e:
        print(str(e))
        sys.exit(1)


@arg('repository')
def containers(args):
    gantry = Gantry(args.base_url)
    for c in gantry.containers(args.repository):
        print(c['Id'])


parser = ArghParser()
parser.add_argument('-b', '--base-url', default=DOCKER_DEFAULT_URL)
parser.add_commands([deploy, containers])


def main():
    parser.dispatch()


if __name__ == '__main__':
    main()
