# -*- coding: utf-8 -*-

from odoo import fields, models


class SaleCapituloWizard(models.TransientModel):
    _name = 'sale.capitulo.wizard'
    _description = 'Wizard Create sale capitulo'


    capitulo_ids = fields.One2many('sale.capitulo.line.wizard', 'capitulo_id')


    def create_sale_capitulo(self):
        sale_order_id = self.env['sale.order'].browse(self._context.get('active_id'))
        for line in self.capitulo_ids:
            if sale_order_id:
                sale_order_id.sale_capitule_line = [(0, 0, {
                    'name': line.name,
                    'comment': line.comment
                })]
                cont = 1
                for line in sale_order_id.sale_capitule_line:
                    line.write({'code': str(cont).zfill(2) if (cont < 10) else str(cont)})
                    cont += 1



class SaleCapituloLineWizard(models.TransientModel):
    _name = 'sale.capitulo.line.wizard'
    _description = 'Wizard Create sale capitulo line'

    capitulo_id = fields.Many2one('sale.capitulo.wizard')
    name = fields.Char(string='Nombre', required=True)
    comment = fields.Text(string="Notas")
