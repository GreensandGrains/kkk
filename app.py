import os
from flask import Flask, render_template, jsonify

# Create the Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Define routes
@app.route('/')
def index():
    """Root route that provides information about the Discord bot."""
    return render_template('index.html')

@app.route('/api/status')
def status():
    """API endpoint that returns the current status of the bot."""
    return jsonify({
        'status': 'online',
        'version': '1.0.0',
        'name': 'Feature-Rich Discord Bot'
    })

# Only run the app if this file is executed directly
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)