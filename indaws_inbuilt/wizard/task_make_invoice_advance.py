# -*- coding: utf-8 -*-
from odoo import models


class TaskAdvancePaymentInv(models.TransientModel):
    _name = "task.advance.payment.inv"
    _description = "Project Task Advance Payment Invoice"


    def create_invoices(self):
        task_ids = self.env['project.task'].browse(self._context.get('active_ids', []))
        task_ids.create_bill_for_material()
        if self._context.get('open_invoices', False):
            return task_ids.action_view_invoice()
        return {'type': 'ir.actions.act_window_close'}
