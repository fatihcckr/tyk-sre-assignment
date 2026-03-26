import json
import socketserver

from kubernetes import client
from http.server import BaseHTTPRequestHandler


class AppHandler(BaseHTTPRequestHandler):
    api_client = None

    def do_GET(self):
        """Catch all incoming GET requests"""
        if self.path == "/healthz":
            self.healthz()
        elif self.path == "/api/deployments/health":
            self.deployments_health()
        else:
            self.send_error(404)

    def healthz(self):
        """Responds with the health status of the application"""
        self.respond(200, "ok")

    def deployments_health(self):
        """Checks whether all deployments have the expected number of ready replicas"""
        apps_v1 = client.AppsV1Api(self.api_client)
        deployments = apps_v1.list_deployment_for_all_namespaces()

        results = []
        for dep in deployments.items:
            expected = dep.spec.replicas or 0
            ready = dep.status.ready_replicas or 0
            results.append({
                "name": dep.metadata.name,
                "namespace": dep.metadata.namespace,
                "expected_replicas": expected,
                "ready_replicas": ready,
                "healthy": ready == expected,
            })

        self.respond_json(200, {"deployments": results})

    def respond(self, status: int, content: str):
        """Writes content and status code to the response socket"""
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()

        self.wfile.write(bytes(content, "UTF-8"))

    def respond_json(self, status: int, data):
        """Writes JSON data and status code to the response socket"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        self.wfile.write(bytes(json.dumps(data), "UTF-8"))


def get_kubernetes_version(api_client: client.ApiClient) -> str:
    """
    Returns a string GitVersion of the Kubernetes server defined by the api_client.

    If it can't connect an underlying exception will be thrown.
    """
    version = client.VersionApi(api_client).get_code()
    return version.git_version


def start_server(address, api_client=None):
    """
    Launches an HTTP server with handlers defined by AppHandler class and blocks until it's terminated.

    Expects an address in the format of `host:port` to bind to.

    Throws an underlying exception in case of error.
    """
    AppHandler.api_client = api_client

    try:
        host, port = address.split(":")
    except ValueError:
        print("invalid server address format")
        return

    with socketserver.TCPServer((host, int(port)), AppHandler) as httpd:
        print("Server listening on {}".format(address))
        httpd.serve_forever()
