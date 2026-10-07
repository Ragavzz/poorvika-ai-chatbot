import importlib.metadata

dists = sorted([d.metadata["Name"] + "==" + d.version for d in importlib.metadata.distributions()])
print(f"Total packages: {len(dists)}")
for p in dists:
    print(p)
