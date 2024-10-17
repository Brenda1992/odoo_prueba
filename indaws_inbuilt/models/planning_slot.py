# Copyright 2023 Indaws - Andrea Ochoa
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class Planning(models.Model):
    _inherit = 'planning.slot'

    parte_id = fields.Many2one('project.task', 'Task')
    deadline = fields.Date(related="parte_id.date_deadline", string="Fecha Limite")
    planned_hours = fields.Float(related="parte_id.planned_hours", string="Horas previstas", widget='float_time')
    planned_hours_task = fields.Float(related="parte_id.planned_hours_task", string="Horas planificadas",widget='float_time')
    hours_left = fields.Float(related="parte_id.hours_left", string="Horas restantes", widget='float_time')
    hours_left_text = fields.Char(compute='_compute_format_hours', string="Horas restantes")
    planned_hours_task_text = fields.Char(compute='_compute_format_hours', string="Horas planificadas")
    planned_hours_text = fields.Char(compute='_compute_format_hours', string="Horas previstas")
    name_task = fields.Char(related="parte_id.name", string="Nombre tarea")

    def format_float_time(self, value):
        pattern = '%02d:%02d'
        if value < 0:
            value = abs(value)
            pattern = '-' + pattern

        hour = int(value)
        minute = round((value % 1) * 60)
        if minute == 60:
            minute = 0
            hour += 1
        return pattern % (hour, minute)

    @api.depends('planned_hours', 'planned_hours_task', 'hours_left')
    def _compute_format_hours(self):
        for item in self:
            item.write({
                'hours_left_text': item.format_float_time(item.hours_left),
                'planned_hours_task_text': item.format_float_time(item.planned_hours_task),
                'planned_hours_text': item.format_float_time(item.planned_hours)
            })