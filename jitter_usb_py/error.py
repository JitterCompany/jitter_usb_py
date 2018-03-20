import time

lookup = {}
def print_error(string, interval_sec=5):
    diff = interval_sec
    if string in lookup:
        diff = time.time() - lookup[string]

    if diff >= interval_sec:
        lookup[string] = time.time()

        print("Error: " + str(string))
