# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import requests
from dateutil import parser
from pytz import timezone, UTC
from markupsafe import Markup
from datetime import timedelta

from odoo import models, fields, _
from odoo.exceptions import UserError


class Meeting(models.Model):
    _inherit = 'calendar.event'

    ms_event_id = fields.Char("Teams Event ID")

    def _get_teams_user(self):
        org_user = self.user_id
        if not org_user:
            raise UserError(_("Microsoft Teams configuration not found for organizer user %s") % org_user.name)

        if all([org_user.client_id, org_user.tenant_id, org_user.client_secret]):
            org_user.check_user_credentials()
            return org_user
        else:
            raise UserError(_("Microsoft Teams configuration not found for organizer user %s") % org_user.name)

    def _prepare_attendees_data(self):
        attendees = [{
            "emailAddress": {
                "address": partner.email.strip(),
                "name": partner.name or partner.email.strip(),
            },
            "type": "required"
        } for partner in self.partner_ids if partner.email]

        if not attendees:
            raise UserError(_("At least one attendee with a valid email is required to create a Teams meeting."))
        return attendees

    def _prepare_meeting_payload(self):
        if not self.start or not self.stop:
            raise UserError(_("Start and end times are required to create a Teams meeting."))

        if self.allday:
            start = {
                "dateTime": self.start.strftime('%Y-%m-%dT00:00:00.0000000'),
                "timeZone": "UTC"
            }
            end = {
                "dateTime": (self.stop + timedelta(days=1)).strftime('%Y-%m-%dT00:00:00.0000000'),
                "timeZone": "UTC"
            }
        else:
            start = {
                "dateTime": self.start.strftime('%Y-%m-%dT%H:%M:%S.%f') + '0',
                "timeZone": "UTC"
            }
            end = {
                "dateTime": self.stop.strftime('%Y-%m-%dT%H:%M:%S.%f') + '0',
                "timeZone": "UTC"
            }

        payload = {
            "subject": self.name or "Untitled Meeting",
            "body": {
                "contentType": "HTML",
                "content": self.description or "Meeting created via Odoo"
            },
            "start": start,
            "end": end,
            "location": {
                "displayName": self.location or "Odoo Virtual Meeting"
            },
            "attendees": self._prepare_attendees_data(),
            "allowNewTimeProposals": True,
            "isOnlineMeeting": True,
            "onlineMeetingProvider": "teamsForBusiness",
            "importance": "normal",
            "sensitivity": "normal",
            "showAs": self.show_as or "busy",
            "isAllDay": self.allday,
        }

        if self.recurrency and self.rrule:
            payload["recurrence"] = self._prepare_teams_recurrence()

        return payload

    def _get_headers(self, include_timezone_preference=False):
        user = self._get_teams_user()
        headers = {
            "Authorization": f"Bearer {user.access_token}",
            "Content-Type": "application/json"
        }

        if include_timezone_preference:
            headers["Prefer"] = "outlook.timezone=UTC"

        return headers

    def _handle_api_error(self, error):
        error_msg = f"Microsoft Teams API request failed: {str(error)}"
        if hasattr(error, 'response') and error.response:
            error_msg += f"\nStatus: {error.response.status_code}\nResponse: {error.response.text}"
        raise UserError(_(error_msg))

    def create_teams_calendar_event(self):
        self.ensure_one()
        organizer_email = self.user_id.email
        url = f"https://graph.microsoft.com/v1.0/users/{organizer_email}/events"
        headers = self._get_headers(include_timezone_preference=True)
        payload = self._prepare_meeting_payload()

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            if self.recurrence_id:
                for event in self.recurrence_id.calendar_event_ids:
                    event.write({
                        'videocall_location': data.get('onlineMeeting', {}).get('joinUrl'),
                        'ms_event_id': data.get('id'),
                        'description': Markup(data.get('body', {}).get('content'))
                    })
            else:
                self.write({
                    'videocall_location': data.get('onlineMeeting', {}).get('joinUrl'),
                    'ms_event_id': data.get('id'),
                    'description': Markup(data.get('body', {}).get('content'))
                })
            return True
        except requests.exceptions.RequestException as e:
            self._handle_api_error(e)

    def update_teams_meeting(self):
        self.ensure_one()
        if not self.ms_event_id:
            raise UserError(_("Cannot update Teams meeting: no Microsoft Event ID associated with this meeting."))

        url = f"https://graph.microsoft.com/v1.0/me/events/{self.ms_event_id}"
        headers = self._get_headers()
        payload = self._prepare_meeting_payload()

        try:
            response = requests.patch(url, headers=headers, json=payload)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            self._handle_api_error(e)

    def delete_teams_meeting(self):
        self.ensure_one()
        if not self.ms_event_id:
            raise UserError(_("Cannot delete Teams meeting: no Microsoft Event ID associated with this meeting."))

        url = f"https://graph.microsoft.com/v1.0/me/events/{self.ms_event_id}"
        headers = self._get_headers()

        try:
            response = requests.delete(url, headers=headers)
        except requests.exceptions.RequestException as e:
            self._handle_api_error(e)
            return

        if response.status_code in [204, 200]:
            if self.recurrence_id:
                self.action_mass_deletion(recurrence_update_setting="all_events")
            else:
                self.unlink()
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'calendar.event',
                'view_mode': 'list',
                'target': 'current',
            }
        else:
            raise UserError(_("Failed to delete Teams meeting. Status: %s\nResponse: %s") % (response.status_code, response.text))

    def _prepare_teams_recurrence(self):
        recurrence_map = {
            'daily': self._prepare_daily_recurrence,
            'monthly': self._prepare_monthly_recurrence,
            'yearly': self._prepare_yearly_recurrence,
            'weekly': self._prepare_weekly_recurrence,
        }

        recurrence_func = recurrence_map.get(self.rrule_type)
        return recurrence_func() if recurrence_func else {}

    def _get_range_data(self):
        range_type_map = {
            'count': 'numbered',
            'end_date': 'endDate',
            'forever': 'noEnd'
        }

        range_type = range_type_map.get(self.end_type)
        if not range_type:
            raise UserError(f"Unsupported end_type: {self.end_type}")

        range_data = {
            'type': range_type,
            'startDate': self.start.strftime('%Y-%m-%d')
        }

        if range_type == 'endDate':
            range_data['endDate'] = self.until.strftime('%Y-%m-%d')
        elif range_type == 'numbered':
            range_data['numberOfOccurrences'] = self.count or 1

        return range_data

    def _prepare_daily_recurrence(self):
        pattern = {
            'type': 'Daily',
            'interval': self.interval or 1,
        }

        return {
            'pattern': pattern,
            'range': self._get_range_data()
        }

    def _prepare_weekly_recurrence(self):
        weekday_map = {
            'Monday': self.mon, 'Tuesday': self.tue, 'Wednesday': self.wed,
            'Thursday': self.thu, 'Friday': self.fri, 'Saturday': self.sat, 'Sunday': self.sun
        }

        pattern = {
            'type': 'weekly',
            'interval': self.interval or 1,
            'daysOfWeek': [day for day, is_selected in weekday_map.items() if is_selected]
        }

        return {
            'pattern': pattern,
            'range': self._get_range_data()
        }

    def _prepare_monthly_recurrence(self):
        if self.month_by == 'date':
            pattern = {
                'type': 'absoluteMonthly',
                'interval': self.interval or 1,
                'dayOfMonth': self.start.day
            }
        elif self.month_by == 'day':
            weekday_map = {
                'MON': 'Monday', 'TUE': 'Tuesday', 'WED': 'Wednesday',
                'THU': 'Thursday', 'FRI': 'Friday', 'SAT': 'Saturday', 'SUN': 'Sunday'
            }

            index_map = {'1': 'first', '2': 'second', '3': 'third', '4': 'fourth', '-1': 'last'}

            pattern = {
                'type': 'relativeMonthly',
                'interval': self.interval or 1,
                'daysOfWeek': [weekday_map.get(self.weekday.upper(), 'Monday')],
                'index': index_map.get(str(self.byday), 'first')
            }
        else:
            raise UserError(f"Unsupported month_by value: {self.month_by}")

        return {
            'pattern': pattern,
            'range': self._get_range_data()
        }

    def _prepare_yearly_recurrence(self):
        pattern = {
            'type': 'absoluteYearly',
            'interval': self.interval or 1,
            'month': self.start.month,
            'dayOfMonth': self.start.day
        }

        return {
            'pattern': pattern,
            'range': self._get_range_data()
        }


class ResUsers(models.Model):
    _inherit = 'res.users'

    def check_user_credentials(self):
        if not self.access_token:
            raise UserError(_("Access token is missing."))
        if self.token_expiry and fields.Datetime.now() > self.token_expiry:
            self.refresh_access_token()

    def _get_headers(self):
        self.check_user_credentials()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def get_teams_meetings(self):
        url = "https://graph.microsoft.com/v1.0/me/events?$select=id,subject,body,start,end,location,attendees,isAllDay,recurrence,onlineMeeting,organizer"
        headers = self._get_headers()

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            meetings_data = response.json()
            if not isinstance(meetings_data, dict):
                raise UserError(_("Unexpected response format from Microsoft Graph API."))

            meetings = meetings_data.get('value')
            if not isinstance(meetings, list):
                raise UserError(_("No meetings data received from Microsoft Graph API."))

            self._sync_teams_meetings_to_calendar(meetings)

            return {'type': 'ir.actions.client', 'tag': 'reload'}

        except Exception as e:
            error_msg = f"Failed to get Teams meetings: {str(e)}"
            if hasattr(e, 'response') and e.response:
                error_msg += f"\nStatus: {e.response.status_code}\nResponse: {e.response.text}"
            raise UserError(_(error_msg))

    def _sync_teams_meetings_to_calendar(self, meetings):
        calendar_event = self.env['calendar.event']
        partner = self.partner_id

        for meeting in meetings:
            ms_event_id = meeting.get('id')
            if not ms_event_id:
                continue

            existing_event = calendar_event.search([('ms_event_id', '=', ms_event_id)], limit=1)

            start_obj, end_obj = meeting.get('start') or {}, meeting.get('end') or {}
            start_str, end_str = start_obj.get('dateTime'), end_obj.get('dateTime')
            start_tz, end_tz = start_obj.get('timeZone', 'UTC'), end_obj.get('timeZone', 'UTC')

            if not start_str or not end_str:
                continue

            try:
                start_dt = timezone(start_tz).localize(parser.parse(start_str)).astimezone(UTC).replace(tzinfo=None)
                end_dt = timezone(end_tz).localize(parser.parse(end_str)).astimezone(UTC).replace(tzinfo=None)
            except Exception:
                continue

            attendees = self._process_meeting_attendees(meeting.get('attendees', []), partner)

            body_obj = meeting.get('body') or {}
            location_obj = meeting.get('location') or {}
            online_meeting_obj = meeting.get('onlineMeeting') or {}
            org_email = self.env['res.users'].search([
                ('email', '=', meeting.get('organizer', {}).get('emailAddress', {}).get('address', ''))
            ], limit=1)

            event_data = {
                'name': meeting.get('subject', 'Untitled Meeting'),
                'description': Markup(body_obj.get('content', '')),
                'start': start_dt,
                'stop': end_dt + timedelta(days=-1) if meeting.get('isAllDay') else end_dt,
                'allday': meeting.get('isAllDay', False),
                'location': location_obj.get('displayName', ''),
                'partner_ids': attendees,
                'ms_event_id': ms_event_id,
                'videocall_location': online_meeting_obj.get('joinUrl', ''),
                'user_id': org_email.id,
            }

            recurrence_obj = meeting.get('recurrence')
            if recurrence_obj:
                event_data.update(self._process_teams_recurrence(recurrence_obj, start_dt))

            try:
                if org_email.login == self.login:
                    if existing_event:
                        existing_event.write(event_data)
                    else:
                        calendar_event.create(event_data)
            except Exception as e:
                raise UserError(_(f"Error creating/updating calendar event: {str(e)}"))

    def _process_meeting_attendees(self, attendees_list, partner):
        attendees = []
        for attendee in attendees_list:
            email_obj = attendee.get('emailAddress')
            if not email_obj:
                continue

            email = email_obj.get('address')
            if not email:
                continue

            attendee_partner = self.env['res.partner'].search([('email', '=', email)], limit=1)
            if not attendee_partner:
                attendee_name = email_obj.get('name', email.split('@')[0])
                attendee_partner = self.env['res.partner'].create({
                    'name': attendee_name,
                    'email': email,
                })
            attendees.append((4, attendee_partner.id))

        if partner.email and not any(p[1] == partner.id for p in attendees if isinstance(p, tuple) and len(p) > 1):
            attendees.append((4, partner.id))

        return attendees

    def _process_teams_recurrence(self, recurrence_obj, start_dt):
        pattern = recurrence_obj.get('pattern', {})
        range_data = recurrence_obj.get('range', {})

        recurrence_type = pattern.get('type', '').lower()
        interval = pattern.get('interval', 1)
        range_type = range_data.get('type', 'noEnd')

        recurrence_data = {
            'recurrency': True,
            'interval': interval,
        }

        if 'daily' in recurrence_type:
            recurrence_data['rrule_type'] = 'daily'
        elif 'weekly' in recurrence_type:
            recurrence_data['rrule_type'] = 'weekly'
            self._set_weekly_recurrence_days(recurrence_data, pattern.get('daysOfWeek', []))
        elif 'monthly' in recurrence_type:
            recurrence_data['rrule_type'] = 'monthly'
            self._set_monthly_recurrence_options(recurrence_data, pattern, recurrence_type, start_dt)
        elif 'yearly' in recurrence_type:
            recurrence_data['rrule_type'] = 'yearly'

        if range_type == 'endDate':
            recurrence_data['end_type'] = 'end_date'
            end_date_str = range_data.get('endDate')
            if end_date_str:
                try:
                    recurrence_data['until'] = parser.parse(end_date_str)
                except Exception:
                    pass
        elif range_type == 'numbered':
            recurrence_data['end_type'] = 'count'
            recurrence_data['count'] = range_data.get('numberOfOccurrences', 1)
        else:
            recurrence_data['end_type'] = 'forever'

        return recurrence_data

    def _set_weekly_recurrence_days(self, recurrence_data, days_of_week):
        day_map = {
            'monday': 'mon', 'tuesday': 'tue', 'wednesday': 'wed',
            'thursday': 'thu', 'friday': 'fri', 'saturday': 'sat', 'sunday': 'sun'
        }

        for day in days_of_week:
            day_lower = day.lower()
            if day_lower in day_map:
                recurrence_data[day_map[day_lower]] = True

    def _set_monthly_recurrence_options(self, recurrence_data, pattern, recurrence_type, start_dt):
        if 'absolutemonthly' in recurrence_type:
            recurrence_data['month_by'] = 'date'
            recurrence_data['day'] = pattern.get('dayOfMonth', start_dt.day)
        else:
            # relativemonthly
            recurrence_data['month_by'] = 'day'

            index_map = {
                'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'last': -1
            }
            recurrence_data['byday'] = index_map.get(pattern.get('index', 'first'), 1)

            weekday_map = {
                'monday': 'MON', 'tuesday': 'TUE', 'wednesday': 'WED',
                'thursday': 'THU', 'friday': 'FRI', 'saturday': 'SAT', 'sunday': 'SUN'
            }

            days = pattern.get('daysOfWeek', [])
            if days and days[0].lower() in weekday_map:
                recurrence_data['weekday'] = weekday_map[days[0].lower()]