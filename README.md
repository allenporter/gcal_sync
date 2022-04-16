# gcal-sync

An asyncio python library for Google Calendar. This library provides a simplified Google Calendar API
that is lighter weight and more streamlined compared to using aiogoogle, and increased reliability by
supporting efficient sync and reading from local storage.


## Development Environment

```bash
$ python3 -m venv venv
$ source venv/bin/activate
$ pip3 install -r requirements.txt

# Run tests
$ py.test

# Run tests with code coverage
$ py.test --cov-report=term-missing --cov=gcal_sync
```
