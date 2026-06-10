from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
os.chdir(r"C:\Dev\LoL_stats\docs")
server = ThreadingHTTPServer(("127.0.0.1", 8000), SimpleHTTPRequestHandler)
server.serve_forever()
