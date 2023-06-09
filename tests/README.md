# How to test

- It is necessary to be activated into Avalon Desktop environment.
- Following are additional dependencies for the testing:

```bash
pip install pytest pytest-asyncio aiohttp aioresponses
```

- Then you can run the tests with the following command:

```bash
pytest -rPx --capture=sys -W ignore::DeprecationWarning .\tests\client\ayon_syncsketch\
```
