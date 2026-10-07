import sys
print("Python:", sys.executable)
print("Version:", sys.version)

for mod in ["datasets", "pandas", "pyarrow", "fastparquet", "requests", "httpx"]:
    try:
        __import__(mod)
        print(f"Module {mod}: available")
    except ImportError:
        print(f"Module {mod}: NOT available")
