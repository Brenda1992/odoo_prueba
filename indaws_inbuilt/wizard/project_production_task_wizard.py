# -*- coding: utf-8 -*-

from odoo import models, fields


class ProjectProductionTaskWizard(models.TransientModel):
    _name = 'project.production.task.wizard'
    _description = 'Project Production_task_wizard'

    def get_project_task_id(self):
        if self._context.get('params') and self._context.get('params').get('id'):
            project_id = self.env['project.project'].browse(self._context.get('params').get('id'))
            if project_id:
                return [('project_id', '=', project_id.id)]
        elif self.env.context.get('project_id', False):
            project_id = self.env['project.project'].browse(self.env.context.get('project_id'))
            if project_id:
                return [('project_id', '=', project_id.id)]
        return []

    task_id = fields.Many2one('project.task', string="Tarea", domain=get_project_task_id)

    def set_task_id(self):
        active_model = self._context.get('active_model')
        if active_model == 'project.production':
            project_production_id = self.env[active_model].browse(self._context.get('active_id'))
            if project_production_id:
                project_production_id.task_id = self.task_id
                # update planned_hours in task
                project_production_ids = self.env['project.production'].search([('task_id', '=', self.task_id.id)])
                planned_hours = 0
                for production in project_production_ids:
                    unid_is_part_hours_ids = production.sale_line_id.unidades_ids.filtered(
                        lambda u: u.product_type_calc.is_part_hours == True
                    )
                    for unidades in unid_is_part_hours_ids:
                        planned_hours += unidades.quantity * production.sale_line_id.product_uom_qty
                self.task_id.planned_hours = planned_hours