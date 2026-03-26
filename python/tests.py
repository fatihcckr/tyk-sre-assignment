import unittest
import socket
import requests

from unittest.mock import MagicMock, patch
from socketserver import TCPServer
from threading import Thread
from kubernetes import client
from kubernetes.client.models import VersionInfo

from app import app


class TestGetKubernetesVersion(unittest.TestCase):
    def test_good_version(self):
        api_client = client.ApiClient()

        version = VersionInfo(
            build_date="",
            compiler="",
            git_commit="",
            git_tree_state="fake",
            git_version="1.25.0-fake",
            go_version="",
            major="1",
            minor="25",
            platform=""
        )
        api_client.call_api = MagicMock(return_value=version)

        version = app.get_kubernetes_version(api_client)
        self.assertEqual(version, "1.25.0-fake")

    def test_exception(self):
        api_client = client.ApiClient()
        api_client.call_api = MagicMock(side_effect=ValueError("test"))

        with self.assertRaisesRegex(ValueError, "test"):
            app.get_kubernetes_version(api_client)


class TestAppHandler(unittest.TestCase):
    def setUp(self):
        super().setUp()

        port = self._get_free_port()
        self.mock_server = TCPServer(("localhost", port), app.AppHandler)

        # Run the mock TCP server with AppHandler on a separate thread to avoid blocking the tests.
        self.mock_server_thread = Thread(target=self.mock_server.serve_forever)
        self.mock_server_thread.daemon = True
        self.mock_server_thread.start()

    def _get_free_port(self):
        """Returns a free port number from OS"""
        s = socket.socket(socket.AF_INET, type=socket.SOCK_STREAM)
        s.bind(("localhost", 0))
        __, port = s.getsockname()
        s.close()

        return port

    def _get_url(self, target):
        """Returns a URL to pass into the requests so that they reach this suite's mock server"""
        host, port = self.mock_server.server_address
        return f"http://{host}:{port}/{target}"

    def tearDown(self):
        self.mock_server.shutdown()
        self.mock_server.server_close()
        super().tearDown()

    def test_healthz_ok(self):
        resp = requests.get(self._get_url("healthz"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, "ok")


class TestReadyz(unittest.TestCase):
    def setUp(self):
        super().setUp()

        self.mock_api_client = MagicMock()
        app.AppHandler.api_client = self.mock_api_client

        port = self._get_free_port()
        self.mock_server = TCPServer(("localhost", port), app.AppHandler)

        self.mock_server_thread = Thread(target=self.mock_server.serve_forever)
        self.mock_server_thread.daemon = True
        self.mock_server_thread.start()

    def tearDown(self):
        self.mock_server.shutdown()
        self.mock_server.server_close()
        app.AppHandler.api_client = None
        super().tearDown()

    def _get_free_port(self):
        s = socket.socket(socket.AF_INET, type=socket.SOCK_STREAM)
        s.bind(("localhost", 0))
        __, port = s.getsockname()
        s.close()
        return port

    def _get_url(self, target):
        host, port = self.mock_server.server_address
        return f"http://{host}:{port}/{target}"

    @patch("app.app.get_kubernetes_version", return_value="1.25.0")
    def test_readyz_ok(self, mock_get_version):
        resp = requests.get(self._get_url("readyz"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, "ok")

    @patch("app.app.get_kubernetes_version", side_effect=Exception("connection refused"))
    def test_readyz_unavailable(self, mock_get_version):
        resp = requests.get(self._get_url("readyz"))
        self.assertEqual(resp.status_code, 503)
        self.assertIn("connection refused", resp.text)


class TestDeploymentsHealth(unittest.TestCase):
    def setUp(self):
        super().setUp()

        self.mock_api_client = MagicMock()
        app.AppHandler.api_client = self.mock_api_client

        port = self._get_free_port()
        self.mock_server = TCPServer(("localhost", port), app.AppHandler)

        self.mock_server_thread = Thread(target=self.mock_server.serve_forever)
        self.mock_server_thread.daemon = True
        self.mock_server_thread.start()

    def tearDown(self):
        self.mock_server.shutdown()
        self.mock_server.server_close()
        app.AppHandler.api_client = None
        super().tearDown()

    def _get_free_port(self):
        s = socket.socket(socket.AF_INET, type=socket.SOCK_STREAM)
        s.bind(("localhost", 0))
        __, port = s.getsockname()
        s.close()
        return port

    def _get_url(self, target):
        host, port = self.mock_server.server_address
        return f"http://{host}:{port}/{target}"

    def _make_deployment(self, name, namespace, replicas, ready_replicas):
        dep = MagicMock()
        dep.metadata.name = name
        dep.metadata.namespace = namespace
        dep.spec.replicas = replicas
        dep.status.ready_replicas = ready_replicas
        return dep

    @patch("app.app.client.AppsV1Api")
    def test_all_healthy(self, mock_apps_v1_class):
        mock_api = MagicMock()
        mock_apps_v1_class.return_value = mock_api

        dep_list = MagicMock()
        dep_list.items = [
            self._make_deployment("web", "default", 3, 3),
            self._make_deployment("api", "production", 2, 2),
        ]
        mock_api.list_deployment_for_all_namespaces.return_value = dep_list

        resp = requests.get(self._get_url("api/deployments/health"))
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertEqual(len(data["deployments"]), 2)
        self.assertTrue(all(d["healthy"] for d in data["deployments"]))

    @patch("app.app.client.AppsV1Api")
    def test_unhealthy_deployment(self, mock_apps_v1_class):
        mock_api = MagicMock()
        mock_apps_v1_class.return_value = mock_api

        dep_list = MagicMock()
        dep_list.items = [
            self._make_deployment("web", "default", 3, 1),
        ]
        mock_api.list_deployment_for_all_namespaces.return_value = dep_list

        resp = requests.get(self._get_url("api/deployments/health"))
        data = resp.json()

        self.assertEqual(len(data["deployments"]), 1)
        dep = data["deployments"][0]
        self.assertEqual(dep["name"], "web")
        self.assertEqual(dep["namespace"], "default")
        self.assertEqual(dep["expected_replicas"], 3)
        self.assertEqual(dep["ready_replicas"], 1)
        self.assertFalse(dep["healthy"])

    @patch("app.app.client.AppsV1Api")
    def test_ready_replicas_none(self, mock_apps_v1_class):
        mock_api = MagicMock()
        mock_apps_v1_class.return_value = mock_api

        dep_list = MagicMock()
        dep_list.items = [
            self._make_deployment("worker", "default", 2, None),
        ]
        mock_api.list_deployment_for_all_namespaces.return_value = dep_list

        resp = requests.get(self._get_url("api/deployments/health"))
        data = resp.json()

        dep = data["deployments"][0]
        self.assertEqual(dep["ready_replicas"], 0)
        self.assertFalse(dep["healthy"])


if __name__ == '__main__':
    unittest.main()
