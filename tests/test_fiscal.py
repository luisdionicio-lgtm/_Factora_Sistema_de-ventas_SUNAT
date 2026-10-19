import pytest
from unittest.mock import patch
from werkzeug.exceptions import BadGateway
from app import create_app
from test_app import account, product, sale


@pytest.fixture
def setup(tmp_path):
    app = create_app({'TESTING':True,'DATABASE':str(tmp_path/'fiscal.db')})
    c,h = account(app)
    pid = product(c,h)
    sid = c.post('/api/sales',headers=h,json=sale(pid)).json['id']
    return app,c,h,sid,pid


def upstream(method,path,data=None,binary=False):
    if path == 'empresa':
        return {'ruc':'20100000001','razon_social':'Emisor de prueba','entorno':'beta','tasa_igv_vigente':18}
    if path == 'series':
        return [{'tipo':'boleta','serie':'B001','activo':True}, {'tipo':'guia_remision','serie':'T001','activo':True}]
    if binary:
        return b'%PDF-1.7\nfake test document'
    return {'id':123,'sunat':{'estado':'aceptado'}}


def test_issue_once_locks_cancellation_and_downloads(setup):
    app,c,h,sid,pid = setup
    with patch('app.fiscal.provider',side_effect=upstream) as mock:
        assert c.post('/api/fiscal/connect',headers=h,json={}).status_code == 200
        url=f'/api/fiscal/issue/{sid}/boleta'
        r=c.post(url,headers=h,json={'serie':'B001'})
        assert r.status_code == 201, r.json
        assert r.json['status'] == 'aceptado'
        assert c.post(url,headers=h,json={'serie':'B001'}).status_code == 409
        assert sum(x.args[0]=='POST' for x in mock.call_args_list) == 1
        sent=next(x.args[2] for x in mock.call_args_list if x.args[0]=='POST')
        assert sent['items'][0]['precio_unitario'] == 118
        assert sent['cliente']['tipo_doc']=='0'
        assert sent['solo_registro'] is False
        assert c.post(f'/api/sales/{sid}/cancel',headers=h,json={}).status_code==409
        assert c.get('/api/products').json[0]['stock']==9
        assert c.get(f'/api/fiscal/documents/{r.json["id"]}/pdf').data.startswith(b'%PDF')


def test_ambiguous_result_never_reissues(setup):
    app,c,h,sid,pid=setup
    def timeout(method,path,*args,**kwargs):
        if method=='POST': raise BadGateway('No response')
        return upstream(method,path,*args,**kwargs)
    with patch('app.fiscal.provider',side_effect=timeout) as mock:
        c.post('/api/fiscal/connect',headers=h,json={})
        url=f'/api/fiscal/issue/{sid}/boleta'
        assert c.post(url,headers=h,json={'serie':'B001'}).status_code==502
        assert c.get('/api/fiscal/documents').json[0]['status']=='POR_VERIFICAR'
        assert c.post(url,headers=h,json={'serie':'B001'}).status_code==409
        assert sum(x.args[0]=='POST' for x in mock.call_args_list)==1


def test_tenant_isolation_csrf_and_link_required(setup):
    app,c,h,sid,pid=setup
    with patch('app.fiscal.provider',side_effect=upstream):
        assert c.post(f'/api/fiscal/issue/{sid}/boleta',headers=h,json={'serie':'B001'}).status_code==409
        assert c.post('/api/fiscal/connect',json={}).status_code==403
        c.post('/api/fiscal/connect',headers=h,json={})
        other,oh=account(app,'other@example.com')
        assert other.post('/api/fiscal/connect',headers=oh,json={}).status_code==409
        assert other.get('/api/fiscal/documents').json==[]
        assert other.get('/api/fiscal/documents/1/pdf').status_code==409


def test_guide_requires_identified_recipient(setup):
    app,c,h,sid,pid=setup
    with patch('app.fiscal.provider',side_effect=upstream) as mock:
        c.post('/api/fiscal/connect',headers=h,json={})
        assert c.post(f'/api/fiscal/issue/{sid}/guia',headers=h,json={'serie':'T001'}).status_code==400
        assert all(x.args[0]!='POST' for x in mock.call_args_list)


def test_private_guide_payload_and_no_second_stock_deduction(setup):
    app,c,h,_,pid=setup
    cid=c.post('/api/customers',headers=h,json={'name':'Destinatario','doc_type':'DNI','document':'12345678'}).json['id']
    sid=c.post('/api/sales',headers=h,json=sale(pid,key='identified',customer_id=cid)).json['id']
    from datetime import datetime,timezone,timedelta
    data={'serie':'T001','fecha_traslado':datetime.now(timezone(timedelta(hours=-5))).date().isoformat(),
          'peso_total':'2.5','partida_ubigeo':'150101','llegada_ubigeo':'150102',
          'partida_direccion':'Origen 123','llegada_direccion':'Destino 123','mod_traslado':'02',
          'conductor_dni':'12345678','conductor_nombres':'Juan','conductor_apellidos':'Perez',
          'licencia':'Q12345678','placa':'ABC123'}
    with patch('app.fiscal.provider',side_effect=upstream) as mock:
        c.post('/api/fiscal/connect',headers=h,json={})
        r=c.post(f'/api/fiscal/issue/{sid}/guia',headers=h,json=data)
        assert r.status_code==201,r.json
        sent=next(x.args[2] for x in mock.call_args_list if x.args[0]=='POST')
        assert sent['conductor']['num_doc']=='12345678'
        assert sent['peso_total']==2.5
        assert 'precio_unitario' not in sent['items'][0]
        assert c.get('/api/products').json[0]['stock']==8


def test_reconcile_checks_reference_and_tenant(setup):
    app,c,h,sid,pid=setup
    def pending(method,path,*args,**kwargs):
        if method=='POST': raise BadGateway('Lost response')
        if path=='boletas/123': return {'id':123,'serie':'B001','observacion':'wrong sale','sunat':{'estado':'aceptado'}}
        return upstream(method,path,*args,**kwargs)
    with patch('app.fiscal.provider',side_effect=pending):
        c.post('/api/fiscal/connect',headers=h,json={})
        c.post(f'/api/fiscal/issue/{sid}/boleta',headers=h,json={'serie':'B001'})
        fid=c.get('/api/fiscal/documents').json[0]['id']
        assert c.post(f'/api/fiscal/documents/{fid}/reconcile',headers=h,json={'remote_id':123}).status_code==409
    def recovered(method,path,*args,**kwargs):
        if path=='boletas/123': return {'id':123,'serie':'B001','observacion':f'Factora venta interna {sid}','sunat':{'estado':'aceptado'}}
        return upstream(method,path,*args,**kwargs)
    with patch('app.fiscal.provider',side_effect=recovered):
        assert c.post(f'/api/fiscal/documents/{fid}/reconcile',headers=h,json={'remote_id':123}).status_code==200
        assert c.get('/api/fiscal/documents').json[0]['status']=='aceptado'


def test_linked_ruc_cannot_be_changed(setup):
    app,c,h,sid,pid=setup
    with patch('app.fiscal.provider',side_effect=upstream):
        c.post('/api/fiscal/connect',headers=h,json={})
        assert c.put('/api/company',headers=h,json={'name':'Otro','ruc':'20999999999'}).status_code==409


def test_refresh_updates_sale_status(setup):
    app,c,h,sid,pid=setup
    with patch('app.fiscal.provider',side_effect=upstream):
        c.post('/api/fiscal/connect',headers=h,json={})
        result=c.post(f'/api/fiscal/issue/{sid}/boleta',headers=h,json={'serie':'B001'})
    def rejected_response(method,path,*args,**kwargs):
        if path.startswith('boletas/'): return {'id':123,'sunat':{'estado':'rechazado'}}
        return upstream(method,path,*args,**kwargs)
    with patch('app.fiscal.provider',side_effect=rejected_response):
        assert c.post(f'/api/fiscal/documents/{result.json["id"]}/refresh',headers=h,json={}).json['status']=='rechazado'
        assert c.get(f'/api/sales/{sid}').json['fiscal_status']=='rechazado'
