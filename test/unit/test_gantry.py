from nose.tools import *
from mock import MagicMock
from mock import call, patch

from gantry.gantry import Gantry, GantryError


MOCK_IMAGES = [
    {'Repository': 'foo',
     'Tag': 'latest',
     'Id': '51f59b5c1b8354c2cc430cc3641fc87a0ad8443465f7b97d9f79ad6263f45548'},
    {'Repository': 'foo',
     'Tag': '124',
     'Id': '51f59b5c1b8354c2cc430cc3641fc87a0ad8443465f7b97d9f79ad6263f45548'},
    {'Repository': 'foo',
     'Tag': '123',
     'Id': 'e79a8874751c79664fdaf56e4af392d3c528fad1830b2588bf05eca876122e3f'},
    {'Repository': 'foo', # untagged image shouldn't break stuff
     'Id': '3d0b615220644b2152cfd146f096d4b813ec87aa981bc43921efd071f7343916'},
]

MOCK_CONTAINERS = [
    {'Image': 'foo:123',
     'Id': '1da4dfe2db6dbf45755f8419e9de4e78f340b4f300783a57e42ead853b46158a'},
    {'Image': 'foo:123',
     'Id': '5e68d8d416da617eeed45f7613f820731fe1d642ff343a43a4a49b55cbb2116e'},
    {'Image': 'e79a8874751c',
     'Id': '60008cffafabaca08174af02d95de22bda6aad09a31a86aeb6b47a6c77f3bec3'},
    {'Image': 'e79', # short id shouldn't be used to match -- too risky
     'Id': '240eeaa7cb8b52d14328d3e4b6b2e4a5432fc52e12da7b0b1db2b6498d03a196'},
    {'Image': 'bar:abc',
     'Id': 'fd677144ec1eeab4c396fa80be8bffb7a55bafb89a99c2ec9bab7c8ad902c8c2'},
]


def copylist(obj):
    return map(lambda x: x.copy(), obj)


class DockerMock(MagicMock):
    def images(self, repo, *args, **kwargs):
        return copylist(filter(lambda im: im['Repository'] == repo, MOCK_IMAGES))

    def containers(self, *args, **kwargs):
        return copylist(MOCK_CONTAINERS)


class TestGantry(object):

    @patch('gantry.gantry.docker.Client')
    def test_fetch_state_images_tags(self, docker_mock):
        docker_mock.return_value = DockerMock()
        g = Gantry()
        images, tags, _ = g.fetch_state('foo')
        assert_equal(3, len(images))
        assert_equal(['123', '124', 'latest'], sorted(tags))
        assert_equal(tags['124'], tags['latest'])

    @patch('gantry.gantry.docker.Client')
    def test_fetch_state_normalises_container_images(self, docker_mock):
        docker_mock.return_value = DockerMock()
        g = Gantry()
        _, _, containers = g.fetch_state('foo')
        assert_equal(3, len(containers))
        for c in containers:
            assert_equal('e79a8874751c79664fdaf56e4af392d3c528fad1830b2588bf05eca876122e3f', c['Image'])

    @patch('gantry.gantry.docker.Client')
    def test_containers(self, docker_mock):
        docker_mock.return_value = DockerMock()
        g = Gantry()
        res = g.containers('foo')
        res_ids = map(lambda x: x['Id'], res)
        assert_equal(['1da4dfe2db6dbf45755f8419e9de4e78f340b4f300783a57e42ead853b46158a',
                      '5e68d8d416da617eeed45f7613f820731fe1d642ff343a43a4a49b55cbb2116e',
                      '60008cffafabaca08174af02d95de22bda6aad09a31a86aeb6b47a6c77f3bec3'],
                     res_ids)

    @patch('gantry.gantry.docker.Client')
    @patch('gantry.gantry.subprocess.Popen')
    def test_deploy(self, popen_mock, docker_mock):
        popen_mock.return_value.wait.return_value = 0
        docker_mock.return_value = client = DockerMock()
        g = Gantry()
        g.deploy('foo', '124', '123')

        client.stop.assert_called_once_with(
            '1da4dfe2db6dbf45755f8419e9de4e78f340b4f300783a57e42ead853b46158a',
            '5e68d8d416da617eeed45f7613f820731fe1d642ff343a43a4a49b55cbb2116e',
            '60008cffafabaca08174af02d95de22bda6aad09a31a86aeb6b47a6c77f3bec3')

        popen_mock.assert_called_with(['docker', 'run', '-d',
            '51f59b5c1b8354c2cc430cc3641fc87a0ad8443465f7b97d9f79ad6263f45548'])
        assert_equal(3, popen_mock.call_count)


    @patch('gantry.gantry.docker.Client')
    def test_deploy_raises_for_unknown_tags(self, docker_mock):
        docker_mock.return_value = client = DockerMock()
        g = Gantry()

        assert_raises(GantryError, g.deploy, 'foo', '125', '123')
        assert_raises(GantryError, g.deploy, 'foo', '124', '122')

    @patch('gantry.gantry.docker.Client')
    @patch('gantry.gantry.subprocess.Popen')
    def test_deploy_error(self, popen_mock, docker_mock):
        popen_mock.return_value.wait.return_value = 1
        docker_mock.return_value = client = DockerMock()
        g = Gantry()

        assert_raises(GantryError, g.deploy, 'foo', '124', '123')
