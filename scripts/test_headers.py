import urllib.request

try:
    response = urllib.request.urlopen("http://localhost:8080/styles.css")
    print("Status:", response.status)
    print("Headers:")
    for header, value in response.getheaders():
        print(f"  {header}: {value}")
except Exception as e:
    print("Error connecting to server:", e)
