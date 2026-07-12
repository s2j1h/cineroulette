from cineroulette import create_app

app = create_app()

if __name__ == "__main__":
    ssl_context = None
    cert_file = app.config["SSL_CERT_FILE"]
    key_file = app.config["SSL_KEY_FILE"]
    if cert_file and key_file:
        ssl_context = (cert_file, key_file)

    app.run(host="0.0.0.0", port=5000, debug=app.debug, threaded=True, ssl_context=ssl_context)
