from odoo import fields, models,api, _,Command
from odoo.exceptions import UserError, ValidationError


class InhHrExpens_pos_wizard(models.TransientModel):
    _inherit ='hr.expense.post.wizard'

    apply_currency_exchange= fields.Boolean("Apply Currency Exchange Rate")

    manual_currency_rate_active = fields.Boolean('Apply Manual Exchange')
    manual_currency_rate = fields.Float('Rate', digits=(12, 6))

    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        readonly=True,
    )

    total_amount_currency = fields.Float('Total')


    @api.model
    def default_get(self, fields_list):
        res = super(InhHrExpens_pos_wizard, self).default_get(fields_list)
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        active_ids = self.env.context.get('active_ids')
        active_model = self.env.context.get('active_model')


        active_id = self.env.context.get('active_id')
        active_model = self.env.context.get('active_model')



        if active_model == 'hr.expense' and active_id:
            expense = self.env['hr.expense'].browse(active_id)
            if expense:
                res['currency_id'] = expense.currency_id.id
                res['total_amount_currency'] = expense.total_amount_currency
        return res








    def action_post_entry(self):
        expenses = self.env['hr.expense'].browse(self.env.context['active_ids'])
        if not self.env['account.move'].has_access('create'):
            raise UserError(_("You don't have the rights to create accounting entries."))
        expense_receipt_vals_list = [
            {
                **new_receipt_vals,
                'journal_id': self.employee_journal_id.id,
                'invoice_date': self.accounting_date,
            }
            for new_receipt_vals in expenses._prepare_receipts_vals()
        ]
        moves = self.env['account.move'].sudo().create(expense_receipt_vals_list)
        moves.is_created_from_expense=True


        for move in moves:
            move._message_set_main_attachment_id(move.attachment_ids, force=True, filter_xml=False)

        if self.apply_currency_exchange:
            # moves.action_post()

            if not self.company_id.expense_journal_id:  # Sets the default one if not specified
                self.sudo().company_id.expense_journal_id = self.employee_journal_id.id

            # Add the company_paid ids to the redirect
            moves_ids = moves.ids + self.env.context.get('company_paid_move_ids', tuple())

            action = {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
            }
            if len(moves_ids) == 1:
                action.update({
                    'name': moves.ref,
                    'view_mode': 'form',
                    'res_id': moves_ids[0],
                })
            else:
                list_view = self.env.ref('hr_expense.view_move_list_expense', raise_if_not_found=False)
                action.update({
                    'name': _("New expense entries"),
                    'view_mode': 'list,form',
                    'views': [(list_view and list_view.id, 'list'), (False, 'form')],
                    'domain': [('id', 'in', moves_ids)],
                })
            return action
        else:

            if not self.company_id.expense_journal_id:  # Sets the default one if not specified
                self.sudo().company_id.expense_journal_id = self.employee_journal_id.id

            # Add the company_paid ids to the redirect
            moves_ids = moves.ids + self.env.context.get('company_paid_move_ids', tuple())

            action = {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
            }
            if len(moves_ids) == 1:
                action.update({
                    'name': moves.ref,
                    'view_mode': 'form',
                    'res_id': moves_ids[0],
                })
            else:
                list_view = self.env.ref('hr_expense.view_move_list_expense', raise_if_not_found=False)
                action.update({
                    'name': _("New expense entries"),
                    'view_mode': 'list,form',
                    'views': [(list_view and list_view.id, 'list'), (False, 'form')],
                    'domain': [('id', 'in', moves_ids)],
                })
            return action

