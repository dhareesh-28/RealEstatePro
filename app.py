import sys
import traceback

try:
    from main_app import app
except Exception as e:
    from flask import Flask
    app = Flask(__name__)
    
    error_traceback = traceback.format_exc()
    print("FATAL ERROR ON STARTUP:", e, file=sys.stderr)
    print(error_traceback, file=sys.stderr)
    
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        return f"<h1>Application Initialization Failed</h1><p>Gunicorn crashed while loading the app. Here is the exact problem we need to fix:</p><pre>{error_traceback}</pre>", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
