# -*- coding: utf-8 -*-

from odoo import models


class WizardCreateObra(models.TransientModel):
    _name = 'wizard.create.obra'
    _description = 'Wizard Create Obra'


    def _create_task_for_chapter(self, capitulo, sale_order):
        project_task = capitulo.task_id
        if not project_task:
            project_task = sale_order.project_id.task_ids.create({
                'project_id': sale_order.project_id.id,
                'name': capitulo.name,
            })
            capitulo.task_id = project_task.id
        return project_task

    def cancel_project_create(self):
        active_id = self._context.get('active_id')
        sale_order = self.env['sale.order'].browse(active_id)
        project = self.env['project.project'].create({
            'name': sale_order.name,
            'partner_id': sale_order.partner_id.id
        })
        sale_order.write({
            'project_id': project.id,
            'analytic_account_id': project.analytic_account_id.id
        })
        if sale_order.company_id.task_creation == 'all':
            for line in sale_order.order_line:
                planned_hours = 0
                unidades_ids = line.unidades_ids.filtered(lambda u: u.product_type_calc.is_part_hours)
                for unidades in unidades_ids:
                    planned_hours += unidades.quantity * line.product_uom_qty
                project_task = self.env['project.task'].create({
                    'project_id': project.id,
                    'name': line.name,
                    'planned_hours': planned_hours
                })
                line.task_id = project_task.id
        elif sale_order.company_id.task_creation == 'task_chapter':
            for capitulo in sale_order.sale_capitule_line:
                project_task = self._create_task_for_chapter(capitulo, sale_order)
                capitulo.line_ids.write({'task_id': project_task.id})
                # Calcular horas planeadas
                planned_hours = 0
                for line in capitulo.line_ids.filtered(lambda l: l.unidades_ids):
                    for unidad in line.unidades_ids.filtered(lambda u: u.product_type_calc.is_part_hours):
                        planned_hours += unidad.quantity * line.product_uom_qty
                project_task.write({'planned_hours': planned_hours})

        if sale_order and sale_order.state in ['sale', 'done'] and sale_order.project_id:
            production_list = [
                (0, 0, {
                    'project_id': sale_order.project_id.id,
                    'sale_line_id': line.id,
                    'name': line.name,
                    'capitulo_id': line.capitulo_id.id,
                    'quantity': line.product_uom_qty,
                    'price_subtotal': line.price_subtotal,
                    'task_id': line.task_id.id
                }) for line in sale_order.order_line]
            sale_order.project_id.project_production_ids = production_list
            sale_order.actulizar_obra()

        if sale_order and sale_order.company_id.sales_based_purchases and sale_order.project_id:
            sale_order.create_task_material()

        if sale_order and sale_order.company_id.task_capitulo_creation == 'all':
            for capitulo in sale_order.sale_capitule_line:
                project_task = self._create_task_for_chapter(capitulo, sale_order)
                capitulo.line_ids.mapped('task_id').write({'parent_id': project_task.id})



