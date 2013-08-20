# @author:  Reno Bowen
#           Gunnar Schaefer

from tg import expose, request
import json

import re
import datetime
import sys

from nimsgears.model import *
from nimsgears.controllers.nims import NimsController

def is_ascii(s):
    # if bool(re.compile(r'^[a-zA-Z\%]+$').match(s)):
    if bool(re.compile(r'^[\w\W\b\B\d\D\s\S]+$').match(s)):
        return True
    else:
        return False
    
def is_a_number(n):
    try:
        int(n)
        return True
    except ValueError:
        return False
        
def is_other_field(n):
    return True
    
            
validation_functions = {
    'Subject Name' : is_ascii,
    'Exam' : is_a_number,
    'Operator' : is_ascii,
    'Subject Age' : is_ascii,
    'PSD Name' : is_ascii,
}


class SearchController(NimsController):

    @expose('nimsgears.templates.search')
    def index(self):
        dataset_cnt = Session.query.count()
        param_list = ['Subject Name', 'Subject Age', 'PSD Name', 'Exam', 'Operator']
        epoch_columns = [('Access', 'col_access'), ('Group', 'col_sunet'), ('Experiment', 'col_exp'), ('Date & Time', 'col_datetime'), ('Subj. Code', 'col_subj'), ('Description', 'col_desc')]
        dataset_columns = [('Data Type', 'col_type')]
        return dict(page='search',
                dataset_cnt=dataset_cnt,
            param_list=param_list,
            epoch_columns=epoch_columns,
            dataset_columns=dataset_columns)
               
    @expose()
    def query(self, **kwargs):
        # For more robust search query parsing, check out pyparsing.
        result = {'success': False}
        if 'search_param' in kwargs and 'search_query' in kwargs and 'date_from' in kwargs and 'date_to' in kwargs:
            search_query = kwargs['search_query']
            search_param = kwargs['search_param']
        else:
            result['error_message'] = 'Fields should be completed before submiting the query.'
            return json.dumps(result)

        if isinstance(search_query, basestring): search_query = [ search_query ]
        if isinstance(search_param, basestring): search_param = [ search_param ]

        #TODO: make sure that search_query has any parameter.

        search_query = [x.replace('*','%') for x in search_query]

        parameters = zip( search_param, search_query )  
        
        db_query = (DBSession.query(Epoch, Session, Subject, Experiment)
                    .join(Session, Epoch.session)
                    .join(Subject, Session.subject)
                    .join(Experiment, Subject.experiment))
                    
        for param, query in parameters:
            if not validation_functions[param](query):
                # The query value is not valid
                result = {'success': False, 'error_message' : 'Your field ' + query + ' is wrong'}
                print result
                return json.dumps(result)
            
            if param == 'PSD Name':
                db_query = db_query.filter(Epoch.psd.ilike( query ))
            elif param == 'Subject Name':                
                db_query = db_query.filter(Subject.lastname.ilike( query ) | Subject.firstname.ilike( query ))
            elif param == 'Exam':
                db_query = db_query.filter(Session.exam == int( query ))
            elif param == 'Operator':
                db_query = (db_query.join(User)
                    .filter(User.uid.ilike(query) | User.firstname.ilike( query ) | User.lastname.ilike( query )))
            elif param == 'Subject Age':
            # TODO: allow more flexibility in age searches. E.g., "34", "34y", "408m", "=34", ">30", "<40", ">30y and <450m", "30 to 40", etc.
                min_age = None
                max_age = None
                a = re.match(r"\s*>(\d+)\s*<(\d+)|\s*>(\d+)|\s*(\d+)\s*to\s*(\d+)|\s*<(\d+)|\s*(\d+)", query )
                if a != None:
                    min_age = max(a.groups()[0:1]+a.groups()[2:4])
                    max_age = max(a.groups()[1:2]+a.groups()[4:5])
                    if min_age==None and max_age==None:
                        min_age = a.groups()[6]
                        max_age = a.groups()[6]
                if min_age==None:
                    min_age = 0
                if max_age==None:
                    max_age = 200
                db_query = (db_query
                    .filter(Session.timestamp - Subject.dob >= datetime.timedelta(days=float(min_age)*365.25))
                    .filter(Session.timestamp - Subject.dob <= datetime.timedelta(days=float(max_age)*365.25)))

            if kwargs['date_from'] != None and re.match(r'\s*\d+\d+',kwargs['date_from'])!=None:
                db_query = db_query.filter(Session.timestamp >= kwargs['date_from'])
            if kwargs['date_to'] != None and re.match(r'\s*\d+\d+',kwargs['date_to'])!=None:
                db_query = db_query.filter(Session.timestamp <= kwargs['date_to'])

            result['data'], result['attrs'] = self._process_result(db_query.all())
            result['success'] = True
        return json.dumps(result)
                
    def _process_result(self, db_result):
        data_list = []
        attr_list = []
        for value in db_result:
            exp = value.Experiment
            sess = value.Session
            subject = value.Subject
            epoch = value.Epoch
            data_list.append(('',
                              exp.owner.gid,
                              exp.name,
                              sess.timestamp.strftime('%Y-%m-%d %H:%M'),
                              subject.code,
                              epoch.description))
            attr_list.append({'id':'epoch=%d' % epoch.id})
        return data_list, attr_list
