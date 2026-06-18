"""Quick timing test to verify the prefetch cache is working."""
import json
import time
import urllib.request


def fetch():
    t0 = time.time()
    res = urllib.request.urlopen("http://127.0.0.1:5000/get-email", timeout=60)
    ms = (time.time() - t0) * 1000
    data = json.loads(res.read())
    return ms, data


if __name__ == "__main__":
    # Wait for the startup prefetch to finish before the first request
    print("Waiting 20s for startup prefetch to complete...")
    time.sleep(20)

    ms1, d1 = fetch()
    print(f"Request 1 (expect CACHE HIT - fast): {ms1:.0f}ms  label={d1['label']}  model={d1.get('_model','?')}")

    # Let the prefetch triggered by request 1 complete
    print("Waiting 20s for next prefetch to complete...")
    time.sleep(20)

    ms2, d2 = fetch()
    print(f"Request 2 (expect CACHE HIT - fast): {ms2:.0f}ms  label={d2['label']}  model={d2.get('_model','?')}")

    print("\nDone. Both requests should be < 200ms if cache hits worked correctly.")
