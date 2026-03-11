"""
Google Calendar integration for SBMS brew tasks.

Uses a Service Account to sync brew tasks to a shared brewery calendar.
All methods fail silently if calendar is not configured or credentials are invalid.

Required .env variables:
  GOOGLE_CALENDAR_ENABLED=true
  GOOGLE_CALENDAR_ID=xxx@group.calendar.google.com
  GOOGLE_SERVICE_ACCOUNT_JSON_B64=<base64-encoded service account JSON>
"""

import os
import base64
import json
import logging

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']

# Google Calendar color IDs
COLOR_ACTIVE    = '5'   # banana (yellow)  – upcoming task
COLOR_COMPLETED = '8'   # graphite (gray)  – completed task


class GCalHandler:
    """Handles all Google Calendar operations for brew tasks."""

    def __init__(self):
        self.enabled     = os.getenv('GOOGLE_CALENDAR_ENABLED', 'false').lower() == 'true'
        self.calendar_id = os.getenv('GOOGLE_CALENDAR_ID', '').strip()
        self._service    = None

        if self.enabled:
            try:
                self._service = self._build_service()
                logger.info('Google Calendar: service initialised successfully')
            except Exception as e:
                logger.warning(f'Google Calendar: failed to initialise – {e}')
                self.enabled = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_service(self):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        b64 = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON_B64', '').strip()
        if not b64:
            raise ValueError('GOOGLE_SERVICE_ACCOUNT_JSON_B64 is not set')

        creds_json = base64.b64decode(b64).decode('utf-8')
        creds_info = json.loads(creds_json)

        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=SCOPES
        )
        return build('calendar', 'v3', credentials=creds, cache_discovery=False)

    def _ready(self):
        return self.enabled and self._service and self.calendar_id

    def _summary(self, brew_name, action, completed=False):
        prefix = '✅ ' if completed else ''
        return f'{prefix}[{brew_name}] {action}'

    def _build_event(self, brew_name, action, notes, scheduled_date, completed=False):
        if hasattr(scheduled_date, 'strftime'):
            date_str = scheduled_date.strftime('%Y-%m-%d')
        else:
            date_str = str(scheduled_date)

        return {
            'summary':     self._summary(brew_name, action, completed),
            'description': notes or '',
            'start':       {'date': date_str},
            'end':         {'date': date_str},
            'colorId':     COLOR_COMPLETED if completed else COLOR_ACTIVE,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_event(self, brew_name, action, notes, scheduled_date):
        """Create a calendar event. Returns the Google Calendar event ID, or None."""
        if not self._ready():
            return None
        try:
            body   = self._build_event(brew_name, action, notes, scheduled_date)
            result = self._service.events().insert(
                calendarId=self.calendar_id, body=body
            ).execute()
            event_id = result.get('id')
            logger.info(f'Google Calendar: created event {event_id} for [{brew_name}] {action}')
            return event_id
        except Exception as e:
            logger.warning(f'Google Calendar create_event failed: {e}')
            return None

    def update_event(self, event_id, brew_name, action, notes, scheduled_date, completed=False):
        """Update an existing calendar event (title, date, colour)."""
        if not self._ready() or not event_id:
            return
        try:
            body = self._build_event(brew_name, action, notes, scheduled_date, completed)
            self._service.events().update(
                calendarId=self.calendar_id, eventId=event_id, body=body
            ).execute()
            logger.info(f'Google Calendar: updated event {event_id}')
        except Exception as e:
            logger.warning(f'Google Calendar update_event failed: {e}')

    def complete_event(self, event_id, brew_name, action, notes, scheduled_date):
        """Mark a calendar event as completed (adds ✅ to title, changes colour to gray)."""
        self.update_event(event_id, brew_name, action, notes, scheduled_date, completed=True)

    def uncomplete_event(self, event_id, brew_name, action, notes, scheduled_date):
        """Undo completion of a calendar event (removes ✅, restores blue colour)."""
        self.update_event(event_id, brew_name, action, notes, scheduled_date, completed=False)

    def delete_event(self, event_id):
        """Delete a calendar event."""
        if not self._ready() or not event_id:
            return
        try:
            self._service.events().delete(
                calendarId=self.calendar_id, eventId=event_id
            ).execute()
            logger.info(f'Google Calendar: deleted event {event_id}')
        except Exception as e:
            logger.warning(f'Google Calendar delete_event failed: {e}')
