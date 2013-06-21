from __future__ import print_function, unicode_literals

import logging
import os
import sys
import subprocess

import docker

DOCKER_DEFAULT_URL = 'http://localhost:4243'

log = logging.getLogger(__name__)


class GantryError(Exception):
    pass


class Gantry(object):

    def __init__(self, docker_url=DOCKER_DEFAULT_URL):
        self.client = docker.Client(docker_url)

    def deploy(self, repository, to_tag, from_tag):
        """
        For the specified repository, spin up as many containers of
        <repository>:<to_tag> as there are currently running containers of
        <repository>:<from_tag>, or just one if there are no currently running
        containers.

        Once the new containers have started, stop the old containers.
        """
        images, tags, containers = self.fetch_state(repository)

        try:
            from_image = tags[from_tag]
        except KeyError:
            raise GantryError('Image %s:%s not found (looking for from_tag)' % (repository, from_tag))
        try:
            to_image = tags[to_tag]
        except KeyError:
            raise GantryError('Image %s:%s not found (looking for to_tag)' % (repository, to_tag))

        from_containers = filter(lambda ct: ct['Image'] == from_image,
                                 containers)
        num_containers = max(1, len(from_containers))

        log.info("Starting %d containers with %s:%s", num_containers, repository, to_tag)

        for i in xrange(num_containers):
            self._start_container(to_image)

        log.info("Started %d containers", num_containers)
        log.info("Shutting down %d old containers with %s:%s", len(from_containers), repository, from_tag)

        self.client.stop(*map(lambda ct: ct['Id'], from_containers))

        log.info("Shut down %d old containers", len(from_containers))

    def containers(self, repository, tag=None):
        """
        Return a list of all currently-running containers for the specified
        repository.
        """
        images, tags, containers = self.fetch_state(repository)
        if tag is None:
            return containers
        return filter(lambda ct: ct['Image'] == tags.get(tag), containers)

    def ports(self, repository, tag=None):
        """
        Return a list of all forwarded ports for currently-running containers
        for the specified repository.
        """
        ports = []
        for c in self.containers(repository, tag=tag):
            if 'Ports' in c:
                ports.extend(_parse_ports(c['Ports']))
        return ports

    def fetch_state(self, repository):
        images, tags = self._fetch_images(repository)
        containers = []
        for c in self.client.containers():
            if ':' in c['Image']:
                # Normalize "repo:tag" Image references to an image id
                repo, tag = c['Image'].split(':', 1)
                if repo != repository:
                    continue
                if tag not in tags:
                    raise GantryError("Found tag %s with no corresponding image entry" % tag)
                c['Image'] = tags[tag]
                containers.append(c)
            else:
                # Normalize short id to full id
                for img_id in images.keys():
                    if len(c['Image']) == 12 and img_id.startswith(c['Image']):
                        c['Image'] = img_id
                        containers.append(c)
        return images, tags, containers

    def _fetch_images(self, repository):
        images = {}
        tags = {}
        for img in self.client.images(repository):
            if img['Id'] not in images:
                images[img['Id']] = img
            try:
                tag = img.pop('Tag')
            except KeyError:
                continue
            tags[tag] = img['Id']
        return images, tags

    def _start_container(self, img_id):
        # FIXME: This should use the HTTP client, but the Python bindings are
        # out of date and don't support run() without a command, which is what
        # we need for our images build with the CMD Dockerfile directive.
        p = subprocess.Popen(['docker', 'run', '-d', img_id])
        retcode = p.wait()
        if retcode != 0:
            raise GantryError("Failed to start container from image %s" % img_id)


def _parse_ports(ports):
    return [map(int, p.split('->', 1)) for p in ports.split(', ')]
