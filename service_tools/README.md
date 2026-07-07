## Service tools
Helper tools to develop syncsketch services or parts of the services.

### How to run
At this moment there is available PowerShell script and Makefile. These scripts depend on the existence of a `./.env`, use `example_env` as template. The contents of the file should be:
```
AYON_SERVER_URL={AYON server url}
AYON_API_KEY={AYON server api key (ideally service user)}
```

### Commands
- `install` - install requirements needed for running processed (requires Git)
- `processor` - start processor

### Processor
Processor of action events to push/pull data to/from syncsketch.
