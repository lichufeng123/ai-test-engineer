# Contributing

Open an issue or pull request with a focused change. Keep public examples synthetic and sanitized.

For framework behavior changes, update `README.md`, `docs/FRAMEWORK.md`, and `framework-manifest.json`, then run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
./bin/ai-test docs-check --root .
```

Do not contribute credentials, private URLs, customer data, execution assets, screenshots, recordings, downloads, or generated caches.
