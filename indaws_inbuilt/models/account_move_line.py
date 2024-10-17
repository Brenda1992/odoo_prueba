# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    #TODO script
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        index=True,
        check_company=True,
        copy=True
    )
    task_id = fields.Many2one('project.task', string="Tarea")  #TODO domain de task_id
    #domain = "[('project_id.analytic_account_id', '=', analytic_account_id)]"


    # def create_analytic_lines(self):
    #     lines_to_create_analytic_entries = self.env['account.move.line']
    #     analytic_line_vals = []
    #     for obj_line in self:
    #         for tag in obj_line.analytic_tag_ids.filtered('active_analytic_distribution'):
    #             for distribution in tag.analytic_distribution_ids:
    #                 analytic_line_vals.append(obj_line._prepare_analytic_distribution_line(distribution))
    #         if obj_line.analytic_account_id:
    #             lines_to_create_analytic_entries |= obj_line
    #
    #     # create analytic entries in batch
    #     if lines_to_create_analytic_entries:
    #         analytic_line_vals += lines_to_create_analytic_entries._prepare_analytic_line()
    #
    #     self.env['account.analytic.line'].with_context(move_done=True).create(analytic_line_vals)
    #     for move in self.purchase_line_id.move_ids:
    #         if move.new_analytic_account_line_id:
    #             move.new_analytic_account_line_id.sudo().unlink()

    def _prepare_analytic_lines(self):
        result = super(AccountMoveLine, self)._prepare_analytic_lines()
        for res in result:
            move_line_id = self.env['account.move.line'].browse(res.get('move_line_id'))
            if move_line_id and move_line_id.purchase_line_id and move_line_id.purchase_line_id.task_id:
                res.update({
                    'po_task_id': move_line_id.purchase_line_id.task_id.id
                })
        return result
