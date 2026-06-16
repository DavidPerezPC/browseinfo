# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import msal
import json

from odoo import http
from odoo.http import request

import logging
_logger = logging.getLogger(__name__)


class TeamsController(http.Controller):

    @http.route('/callback', type='http', auth='public', csrf=False)
    def teams_callback(self, **kw):
        """Handle the callback from Microsoft authentication"""
        _logger.info("Received callback from Microsoft OAuth")

        code = kw.get('code')
        error = kw.get('error')
        error_description = kw.get('error_description')
        state = kw.get('state', '')

        # Extract user ID from state
        user_id = None
        if state and '_' in state:
            try:
                user_id = int(state.split('_')[0])
                _logger.info(f"Extracted user ID {user_id} from state")
            except (ValueError, IndexError):
                _logger.error("Invalid state parameter format")

        if error:
            _logger.error(f"OAuth error: {error} - {error_description}")
            return http.Response(
                f"<html><body><h1>Authentication Error</h1><p>{error}: {error_description}</p></body></html>",
                status=400
            )

        if not code:
            _logger.error("No authorization code received in callback")
            return http.Response(
                "<html><body><h1>Authentication Error</h1><p>No authorization code received</p></body></html>",
                status=400
            )

        # Find the specific user that initiated this auth flow
        user = None
        if user_id:
            user = request.env['res.users'].sudo().browse(user_id).exists()
            _logger.info(f"Found user by ID: {bool(user)}")

        if not user:
            _logger.error("No user with Microsoft Teams configuration found")
            return http.Response(
                "<html><body><h1>Configuration Error</h1><p>No user with Microsoft Teams configuration found</p></body></html>",
                status=500
            )

        try:
            if not user.auth_flow:
                _logger.error(f"No auth flow data found for user ID {user.id}")
                return http.Response(
                    "<html><body><h1>Authentication Error</h1><p>No authentication flow data found. Please start the authentication process again.</p></body></html>",
                    status=400
                )

            flow_data = json.loads(user.auth_flow)

            app = msal.ConfidentialClientApplication(
                user.client_id,
                authority=f"https://login.microsoftonline.com/{user.tenant_id}",
                client_credential=user.client_secret,
            )

            result = app.acquire_token_by_auth_code_flow(
                flow_data,
                kw,
            )

            if "error" in result:
                _logger.error(f"Error acquiring token: {result.get('error')} - {result.get('error_description')}")
                return http.Response(
                    f"<html><body><h1>Token Error</h1><p>{result.get('error')}: {result.get('error_description')}</p></body></html>",
                    status=400
                )

            access_token = result.get('access_token')
            refresh_token = result.get('refresh_token')
            expires_in = result.get('expires_in')

            if access_token and expires_in:
                expiry = user._get_token_expiry(expires_in)

                user.sudo().write({
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'token_expiry': expiry,
                    'auth_flow': '',
                })
                _logger.info(f"Successfully updated tokens for user ID {user.id}")

                menu_id = ''
                cids = user.company_id.id

                # Create a dynamic redirect URL to the user form view
                try:
                    action_xmlid = 'base.action_res_users'
                    action = request.env.ref(action_xmlid)
                    action_id = action.id
                except:
                    action = request.env['ir.actions.act_window'].search([
                        ('res_model', '=', 'res.users'),
                        ('name', 'ilike', 'Users')
                    ], limit=1)
                    action_id = action.id

                    menu_xmlids = [
                        'base.menu_action_res_users',
                        'base.menu_users',
                        'base.menu_res_users_act_window'
                    ]

                    for xmlid in menu_xmlids:
                        try:
                            menu = request.env.ref(xmlid)
                            menu_id = menu.id
                            break
                        except:
                            continue

                url = '/web#id=%s&cids=%s&menu_id=%s&action=%s&model=res.users&view_type=form' % (user.id, cids, menu_id, action_id)
                return request.redirect(url)

            else:
                _logger.error("No access token or expiry received in token response")
                return http.Response(
                    "<html><body><h1>Token Error</h1><p>No access token received</p></body></html>",
                    status=400
                )

        except Exception as e:
            _logger.exception(f"Exception in callback processing: {str(e)}")
            return http.Response(
                f"<html><body><h1>Error</h1><p>An error occurred: {str(e)}</p></body></html>",
                status=500
            )
