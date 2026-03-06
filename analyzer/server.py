import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

_config = None
_current_report = None


class AnalyzerHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_file("web/index.html", "text/html")
        elif path == "/style.css":
            self._serve_file("web/style.css", "text/css")
        elif path == "/app.js":
            self._serve_file("web/app.js", "application/javascript")
        elif path == "/api/report":
            self._json_response(_current_report)
        elif path == "/api/reports":
            from analyzer.storage import list_reports
            reports = list_reports(_config)
            self._json_response(reports)
        elif path == "/api/report/load":
            filepath = query.get("path", [None])[0]
            if filepath and os.path.exists(filepath):
                from analyzer.storage import load_report
                self._json_response(load_report(filepath))
            else:
                self._json_response({"error": "Report not found"}, 404)
        elif path == "/api/diff":
            self._handle_diff(query)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/reload":
            self._handle_reload()
        else:
            self.send_error(404)

    def _handle_diff(self, query):
        a_path = query.get("a", [None])[0]
        b_path = query.get("b", [None])[0]
        if not a_path or not b_path:
            self._json_response({"error": "Need both ?a=path&b=path"}, 400)
            return

        from analyzer.storage import load_report
        from analyzer.diff import diff_reports

        if not os.path.exists(a_path) or not os.path.exists(b_path):
            self._json_response({"error": "Report file not found"}, 404)
            return

        old = load_report(a_path)
        new = load_report(b_path)
        result = diff_reports(old, new)
        self._json_response(result)

    def _handle_reload(self):
        global _current_report
        from analyzer.parser import parse_build_layout
        from analyzer.report import generate_report
        from analyzer.storage import save_report

        layout_path = _config["buildlayout_path"]
        if not os.path.exists(layout_path):
            self._json_response({"error": f"File not found: {layout_path}"}, 404)
            return

        parsed = parse_build_layout(layout_path)
        _current_report = generate_report(parsed)
        _current_report["project_name"] = _config["project_name"]
        save_report(_current_report, _config)
        self._json_response({"status": "ok", "summary": _current_report["summary"]})

    def _serve_file(self, filepath, content_type):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, filepath)
        if not os.path.exists(full_path):
            self.send_error(404)
            return
        with open(full_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def _json_response(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def start_server(config, report=None):
    global _config, _current_report
    _config = config
    _current_report = report

    server = HTTPServer(("0.0.0.0", config["port"]), AnalyzerHandler)
    print(f"Server running at http://localhost:{config['port']}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()
