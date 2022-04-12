# Google Calendar Sync Design

## Objective

The idea is to replace the current google calendar APIs with support for local sync.

Goals:
- Improve availability of calendar data, removing some reliance on cloud
- Improve performance, reducing overhead of API calls
- Improve consistency across calendar entity attribtues (e.g. state, event fetch)

Non-Goals:
- Will not improve availabilty of mutate operations
- No bi-directional sync
- Local calendar support
- Resolve issues in calendar entity state (e.g. concurrent events)

## Background

The google calendar entity today has two calls that may operate differently: The async_get_events call returns a live view, and the current entity is updated every 5 minutes and returns the next starting event.

## Overview

The overall solution proposed will still rely on a poll to the calendar API, however it will instead use the sync and pagination APIs.

On initialziation of a new calendar, the calendar worker initiate a sync and hold on to the sync token. It will then run a sync and page through all items until all pages are complete. For each event returned from the page, the event will either be added, updated, or removed from the local database.

## Detailed Design

We will want a mechanism to "force sync" for serving the calendar database in the UI.

The local database needs to support two operations:
- Next upcoming event
- All events within a start/end date range

The database should have two indexes to serve the above queries:
- Events indexed by start time
- Events indexed by end time

Additionally, the database needs to support insert, update, delete to support the sync APIs.

TODO: Can the list of calendars also be sync'd?
