import mimetypes

mime, encoding = mimetypes.guess_type("styles.css")
print(f"MIME type for styles.css: '{mime}'")
