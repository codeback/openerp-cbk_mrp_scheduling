# -*- encoding: utf-8 -*-
##############################################################################
#
#    res_partner
#    Copyright (c) 2013 Codeback Software S.L. (http://codeback.es)    
#    @author: Miguel García <miguel@codeback.es>
#    @author: Javier Fuentes <javier@codeback.es>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv
from datetime import datetime, timedelta
from openerp.tools.translate import _

import pytz

class mrp_production(osv.osv):
    _name = 'mrp.production'
    _inherit = "mrp.production"

    def create (self, cr, uid, data, context=None):    
        args = []
        last_productions_id = self.search(cr, uid, args, order='date_planned desc', limit=1)[0]  
        last_productions = self.browse(cr, uid, last_productions_id)        

        date_planned = datetime.strptime(last_productions.date_planned, '%Y-%m-%d %H:%M:%S') + timedelta(hours=last_productions.hour_total)
        data["date_planned"] = date_planned.strftime('%Y-%m-%d %H:%M:%S')
                
        mrp_prod = super(mrp_production, self).create(cr, uid, data, context=context)
        self.reorder_productions(cr, uid, date_start_from=date_planned, date_start_to=date_planned, context=context)
        return mrp_prod

    # def action_confirm(self, cr, uid, ids, context=None):
    #     
    #     shipment_id = super(mrp_production, self).action_confirm(cr, uid, ids, context=context)

    #     self.reorder_productions(cr, uid)

    #     return shipment_id

    def reorder_productions(self, cr, uid, date_start_from=datetime.now(), date_start_to=datetime.now(), context=None):

        work_sched_model = self.pool.get('resource.calendar')
        work_sched_ids = work_sched_model.search(cr, uid, [("name", "=", "Fábrica")])      
            
        if len(work_sched_ids) > 0:
            work_sched = work_sched_model.browse(cr, uid, work_sched_ids)[0]
            
            str_date_start_from = datetime.strftime(date_start_from, '%Y-%m-%d %H:%M:%S')
            
            args = [('date_planned', '>=', str_date_start_from), 
                ('state', '!=', "in_production"), 
                ('state', '!=', "done")
            ]
            
            productions_ids = self.search(cr, uid, args, order='date_planned asc')
            productions = self.browse(cr, uid, productions_ids)

            for i, production in enumerate(productions):

                # Calcular fecha de inicio del trabajo
                if i < 1:
                    date_planned = date_start_to #datetime.strptime(production.date_planned, '%Y-%m-%d %H:%M:%S')
                    week_day = date_planned.isocalendar()[2]
                    if week_day > 5:
                        offset_hours = (week_day-5) * 24
                        week_day = 1
                        start_hour = work_sched.attendance_ids[week_day-1].hour_from   
                        date_planned = self._date_conversion(date_planned.replace(hour=0, minute=0, second=0, microsecond=0), offset_hours+start_hour)

                else:
                    date_planned = date_planned + timedelta(hours=productions[i-1].hour_total)                    
                
                # Calcular fecha de fin del trabajo
                end_hour = work_sched.attendance_ids[week_day-1].hour_to             
                end_last_work = self._date_conversion(date_planned, production.hour_total, localize=False)
                end_date = self._date_conversion(date_planned.replace(hour=0, minute=0, second=0, microsecond=0), end_hour)

                # Si el trabajo termina más tarde que la jornada laboral
                # se pasa al siguiente día
                if end_last_work > end_date:
                    week_day = week_day + 1 

                    if week_day > 5:
                        # Hoy es viernes
                        offset_hours = 3 * 24
                        week_day = 1
                    else:
                        offset_hours = 24
                        
                    start_hour = work_sched.attendance_ids[week_day-1].hour_from   
                    date_planned = self._date_conversion(date_planned.replace(hour=0, minute=0, second=0, microsecond=0), offset_hours+start_hour)

                # Actualizar fecha de inicio del trabajo
                self.write(cr, uid, production.id, {'date_planned': date_planned.strftime('%Y-%m-%d %H:%M:%S')})

    def _date_conversion(self, date, hours, localize=True):        

        local = pytz.timezone ("Europe/Madrid")
        utc = pytz.UTC
        local = local if localize else utc

        date = date.replace(tzinfo=None)
        end_date = date + timedelta(hours=hours)
        local_dt = local.localize(end_date, is_dst=None)

        return local_dt.astimezone (pytz.utc)

class mrp_production_scheduler(osv.osv_memory):
    _name = "mrp.production.scheduler"
    _columns = {
        'start_from': fields.datetime('Start Date from', required=True),
        'start_to': fields.datetime('Start Date To', required=True)        
    } 
    
    _defaults = {
        'start_from' : datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S'),
        'start_to': datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S'),
    }

    def reorder_production_queue(self, cr, uid, ids, context=None):
        """ reorder production queue from wizard"""    

        obj = self.pool.get('mrp.production')
        data = self.browse(cr, uid, ids, context=context)[0]      

        start_from = datetime.strptime(data.start_from, '%Y-%m-%d %H:%M:%S')
        start_to = datetime.strptime(data.start_to, '%Y-%m-%d %H:%M:%S')

        obj.reorder_productions(cr, uid, date_start_from=start_from, date_start_to=start_to, context=context)
        
        menu_mod = self.pool.get('ir.ui.menu')        
        args = [('name', '=', 'Order Planning')]
        menu_ids = menu_mod.search(cr, uid, args)
        
        return {
            'name': 'Order Planning',
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {'menu_id': menu_ids[0]},
        }      
