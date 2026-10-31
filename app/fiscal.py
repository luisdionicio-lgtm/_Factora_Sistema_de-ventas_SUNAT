"""Server-side Kodevo adapter. Credentials never leave this process."""
import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from flask import Blueprint, abort, current_app, g, jsonify, request, Response
from .db import row, rows, get_db, Transaction
from .security import protect, audit
from .services import text, integer

bp = Blueprint('fiscal', __name__)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def provider(method, path, data=None, binary=False):
    config = current_app.config.get('FISCAL_CONFIG')
    if config is None:
        file = Path(__file__).parent.parent / 'data' / 'fiscal-secrets.json'
        config = json.loads(file.read_text(encoding='utf-8')) if file.exists() else {}
    key = os.environ.get('FISCAL_API_KEY', config.get('api_key', ''))
    secret = os.environ.get('FISCAL_API_SECRET', config.get('api_secret', ''))
    if not key or not secret:
        abort(503, description='Faltan las credenciales del proveedor en el servidor.')
    req = Request('https://sunat.kodevo.es/api/v1/' + path, method=method,
                  data=json.dumps(data).encode() if data is not None else None,
                  headers={'Accept': 'application/json', 'Content-Type': 'application/json',
                           'X-Api-Key': key, 'X-Api-Secret': secret, 'User-Agent': 'Factora/1.0'})
    try:
        with build_opener(NoRedirect).open(req, timeout=35) as response:
            body = response.read(12 * 1024 * 1024 + 1)
            if len(body) > 12 * 1024 * 1024:
                abort(502, description='El archivo del proveedor supera el límite permitido.')
            if binary:
                return body
            result = json.loads(body)
            if result.get('estado') not in (None, 'exito', 'success'):
                abort(422, description='El proveedor no completó la operación. Revisa el documento en su panel.')
            return result.get('datos', result)
    except HTTPError as error:
        # Do not echo upstream responses: they can contain personal data or credentials.
        abort(422 if error.code in (400, 422) else 502,
              description=f'El proveedor respondió HTTP {error.code}. Revisa los datos y el panel del proveedor antes de repetir una emisión.')
    except (URLError, TimeoutError, OSError, ValueError):
        abort(502, description='No se pudo confirmar la respuesta del proveedor. Consulta su panel antes de repetir la emisión.')


def initialize_fiscal():
    get_db().executescript('''
    CREATE TABLE IF NOT EXISTS fiscal_accounts(
      company_id INTEGER PRIMARY KEY REFERENCES companies(id), ruc TEXT UNIQUE NOT NULL);
    CREATE TABLE IF NOT EXISTS fiscal_documents(
      id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id),
      sale_id INTEGER NOT NULL REFERENCES sales(id), kind TEXT NOT NULL,
      remote_id INTEGER, status TEXT NOT NULL, payload TEXT NOT NULL,
      response TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(company_id,sale_id,kind));
    ''')


@bp.before_request
def restrict_emitter():
    # The server owner explicitly assigns global provider credentials to a tenant.
    # Registration or being an admin is never enough to claim those credentials.
    from .security import protect
    @protect(admin=True)
    def check():
        allowed = current_app.config.get('FISCAL_COMPANY_ID', os.environ.get('FISCAL_COMPANY_ID', ''))
        if str(g.company) != str(allowed):
            abort(403, description='El servidor no ha autorizado la integración fiscal para este negocio.')
    return check()


def account():
    a = row('SELECT * FROM fiscal_accounts WHERE company_id=?', (g.company,))
    if not a:
        abort(409, description='Vincula primero tu negocio en Emisión electrónica.')
    p = provider('GET', 'empresa')
    if str(p.get('ruc')) != a['ruc']:
        abort(409, description='Las credenciales corresponden a otro emisor.')
    return p


@bp.get('/api/fiscal/profile')
@protect(admin=True)
def profile():
    p = provider('GET', 'empresa')
    a = row('SELECT * FROM fiscal_accounts WHERE company_id=?', (g.company,))
    return jsonify(company={k: p.get(k) for k in ('ruc','razon_social','direccion','entorno','tiene_certificado','tasa_igv_vigente')},
                   linked=bool(a and a['ruc'] == str(p.get('ruc'))))


@bp.post('/api/fiscal/connect')
@protect(admin=True)
def connect():
    p = provider('GET', 'empresa')
    with Transaction() as db:
        local = row('SELECT * FROM companies WHERE id=?', (g.company,))
        if local['ruc'] and local['ruc'] != str(p['ruc']):
            abort(409, description='El RUC local no coincide con el emisor. Revisa Configuración.')
        db.execute('INSERT OR IGNORE INTO fiscal_accounts(company_id,ruc) VALUES(?,?)', (g.company, p['ruc']))
        if not row('SELECT * FROM fiscal_accounts WHERE company_id=? AND ruc=?', (g.company,p['ruc'])):
            abort(409, description='Este emisor ya está vinculado a otro negocio local.')
        db.execute('UPDATE companies SET ruc=?,name=?,address=? WHERE id=?',
                   (p['ruc'],p['razon_social'],p.get('direccion') or '',g.company))
        audit('EMISOR_VINCULADO', str(p['ruc']))
    return jsonify(ok=True)


@bp.get('/api/fiscal/series')
@protect(admin=True)
def series():
    account()
    return jsonify(provider('GET','series'))


@bp.get('/api/fiscal/documents')
@protect(admin=True)
def documents():
    get_db().execute("UPDATE fiscal_documents SET status='POR_VERIFICAR' WHERE company_id=? AND status='ENVIANDO' AND datetime(created_at)<datetime('now','-2 minutes')", (g.company,))
    docs = rows('SELECT id,sale_id,kind,remote_id,status,response,created_at FROM fiscal_documents WHERE company_id=? ORDER BY id DESC LIMIT 1000', (g.company,))
    for doc in docs:
        source = json.loads(doc['response'] or '{}')
        sunat = source.get('sunat') or {}
        doc['response'] = json.dumps({'numero_completo': source.get('numero_completo'),
            'sunat': {key: sunat.get(key) for key in ('estado','codigo','descripcion')}})
    return jsonify(docs)


def sale_payload(sale):
    c = json.loads(sale['customer_snapshot'])
    kind = {'DNI':'1','RUC':'6'}.get(c.get('doc_type'),'0')
    return {'tipo_doc':kind, 'num_doc':c.get('document') if kind != '0' else '99999999',
            'razon_social':c['name'], 'direccion':c.get('address','')}


def remote_status(result):
    sunat = result.get('sunat') or {}
    return str(sunat.get('estado') or sunat.get('status') or result.get('sunat_status') or result.get('estado') or 'PENDIENTE')


@bp.post('/api/fiscal/issue/<int:sid>/<kind>')
@protect(admin=True)
def issue(sid, kind):
    if kind not in ('boleta','guia'):
        abort(404)
    p = account()
    d = request.get_json()
    if not isinstance(d,dict):
        abort(400)
    s = row('SELECT * FROM sales WHERE id=? AND company_id=?', (sid,g.company))
    if not s or s['status'] != 'registrado':
        abort(409, description='Selecciona una venta registrada de tu negocio.')
    if kind == 'boleta' and s['kind'] != 'boleta':
        abort(400, description='Selecciona una venta de tipo boleta.')
    if kind == 'boleta' and float(p.get('tasa_igv_vigente',18)) != 18:
        abort(409, description='Esta venta usa IGV 18%; el régimen del proveedor usa otra tasa.')
    serie = text(d,'serie',4)
    available = provider('GET','series')
    if not any(x.get('activo') and x.get('serie') == serie and x.get('tipo') == ('boleta' if kind == 'boleta' else 'guia_remision') for x in available):
        abort(400, description='Selecciona una serie activa del tipo correspondiente.')
    today = datetime.now(timezone(timedelta(hours=-5))).date().isoformat()
    payload = {'serie':serie,'fecha_emision':today,'enviar_automatico':True,
               'observacion':f'Factora venta interna {sid}', 'items':[]}
    for i in rows('SELECT * FROM sale_items WHERE sale_id=?',(sid,)):
        item = {'codigo':i['sku'],'descripcion':i['name'],'unidad':'NIU','cantidad':i['quantity']}
        if kind == 'boleta':
            item.update(precio_unitario=i['price']/100,tip_afe_igv='10')
        payload['items'].append(item)
    if kind == 'boleta':
        payload.update(cliente=sale_payload(s),tipo_moneda='PEN',forma_pago='Contado',solo_registro=False)
    else:
        recipient = sale_payload(s)
        if recipient['tipo_doc'] == '0':
            abort(400, description='La guía requiere destinatario con DNI o RUC en la venta.')
        payload.update(destinatario=recipient, cod_traslado='01',und_peso_total='KGM')
        for name in ('fecha_traslado','partida_ubigeo','partida_direccion','llegada_ubigeo','llegada_direccion','mod_traslado'):
            payload[name] = text(d,name,250)
        try:
            date = datetime.strptime(payload['fecha_traslado'],'%Y-%m-%d').date()
            weight = float(d.get('peso_total',0))
            if date.isoformat() < today or not 0 < weight <= 1000000:
                raise ValueError()
        except (ValueError,TypeError):
            abort(400,description='Revisa la fecha de traslado y el peso positivo en kg.')
        payload['peso_total'] = weight
        if not all(re.fullmatch(r'\d{6}',payload[k]) for k in ('partida_ubigeo','llegada_ubigeo')):
            abort(400,description='Los ubigeos deben tener 6 dígitos.')
        if payload['mod_traslado'] == '01':
            ruc = text(d,'transportista_ruc',11)
            if not re.fullmatch(r'\d{11}',ruc):
                abort(400,description='El transportista necesita un RUC de 11 dígitos.')
            payload['transportista'] = {'tipo_doc':'6','num_doc':ruc,'razon_social':text(d,'transportista_nombre'),'nro_mtc':text(d,'nro_mtc',40)}
            payload['fecha_de_entrega_al_transportista'] = payload['fecha_traslado']
        elif payload['mod_traslado'] == '02':
            dni = text(d,'conductor_dni',8)
            if not re.fullmatch(r'\d{8}',dni):
                abort(400,description='El conductor necesita un DNI de 8 dígitos.')
            payload['vehiculo'] = {'placa':text(d,'placa',10)}
            payload['conductor'] = {'tipo':'Principal','tipo_doc':'1','num_doc':dni,
                'nombres':text(d,'conductor_nombres'),'apellidos':text(d,'conductor_apellidos'),'licencia':text(d,'licencia',30)}
        else:
            abort(400,description='Modalidad de traslado inválida.')
    with Transaction() as db:
        current_sale = row('SELECT status FROM sales WHERE id=? AND company_id=?',(sid,g.company))
        if not current_sale or current_sale['status'] != 'registrado':
            abort(409,description='La venta fue anulada mientras preparabas el documento.')
        existing = row('SELECT * FROM fiscal_documents WHERE company_id=? AND sale_id=? AND kind=?',(g.company,sid,kind))
        if existing:
            abort(409,description='Esta venta ya tiene una solicitud de este tipo. Consulta su estado antes de crear otra.')
        fid = db.execute('INSERT INTO fiscal_documents(company_id,sale_id,kind,status,payload) VALUES(?,?,?,?,?)',
            (g.company,sid,kind,'ENVIANDO',json.dumps(payload))).lastrowid
        # Lock cancellation before any external side effect, including a guide.
        db.execute("UPDATE sales SET fiscal_status='EN_PROCESO' WHERE id=?",(sid,))
    try:
        result = provider('POST','boletas' if kind == 'boleta' else 'guias-remision',payload)
        remote = result.get('id') if isinstance(result,dict) else None
        if not isinstance(remote,int):
            abort(502,description='El proveedor no devolvió un ID verificable. Revisa su panel.')
    except Exception:
        get_db().execute("UPDATE fiscal_documents SET status='POR_VERIFICAR' WHERE id=?",(fid,))
        raise
    status = remote_status(result)
    with Transaction() as db:
        db.execute('UPDATE fiscal_documents SET remote_id=?,status=?,response=? WHERE id=?', (remote,status,json.dumps(result),fid))
        db.execute('UPDATE sales SET fiscal_status=? WHERE id=?',(status,sid))
        audit('EMISION_'+kind.upper(),str(fid))
    return jsonify(id=fid,status=status),201


def document(fid):
    account()
    doc = row('SELECT * FROM fiscal_documents WHERE id=? AND company_id=?',(fid,g.company))
    if not doc or not doc['remote_id']:
        abort(409,description='No hay ID confirmado. Verifica el documento en el panel del proveedor.')
    return doc, ('boletas' if doc['kind']=='boleta' else 'guias-remision')+'/'+str(doc['remote_id'])


@bp.post('/api/fiscal/documents/<int:fid>/reconcile')
@protect(admin=True)
def reconcile(fid):
    account()
    doc = row('SELECT * FROM fiscal_documents WHERE id=? AND company_id=?',(fid,g.company))
    if not doc or doc['remote_id'] or doc['status'] != 'POR_VERIFICAR':
        abort(409,description='Este documento no requiere conciliación manual.')
    d = request.get_json()
    if not isinstance(d,dict): abort(400)
    rid = integer(d.get('remote_id'),'ID del proveedor',1)
    path = ('boletas' if doc['kind']=='boleta' else 'guias-remision')+'/'+str(rid)
    result = provider('GET',path)
    original = json.loads(doc['payload'])
    if result.get('observacion') != original['observacion'] or result.get('serie') != original['serie']:
        abort(409,description='El documento del proveedor no coincide con esta solicitud de Factora.')
    with Transaction() as db:
        db.execute('UPDATE fiscal_documents SET remote_id=?,status=?,response=? WHERE id=?',
                   (rid,remote_status(result),json.dumps(result),fid))
        audit('CONCILIACION_FISCAL',str(fid))
    return jsonify(ok=True)


@bp.post('/api/fiscal/documents/<int:fid>/refresh')
@protect(admin=True)
def refresh(fid):
    doc,path = document(fid)
    if doc['kind']=='guia':
        provider('GET',path+'/estado')
    result = provider('GET',path)
    status = remote_status(result)
    with Transaction() as db:
        db.execute('UPDATE fiscal_documents SET status=?,response=? WHERE id=?',(status,json.dumps(result),fid))
        db.execute('UPDATE sales SET fiscal_status=? WHERE id=? AND company_id=?',(status,doc['sale_id'],g.company))
    return jsonify(status=status)


@bp.get('/api/fiscal/documents/<int:fid>/<format>')
@protect(admin=True)
def download(fid,format):
    if format not in ('pdf','xml','cdr','ticket'):
        abort(404)
    doc,path = document(fid)
    ext = 'pdf' if format=='ticket' else format
    suffix = '/pdf?format=ticket-80' if format=='ticket' else '/'+format
    if format == 'pdf': suffix += '?format=a4'
    body = provider('GET',path+suffix,binary=True)
    expected = {'pdf':b'%PDF','xml':b'<','cdr':b'PK'}[ext]
    if not body.lstrip().startswith(expected):
        abort(502,description='El proveedor aún no entregó el archivo solicitado.')
    return Response(body,mimetype={'pdf':'application/pdf','xml':'application/xml','cdr':'application/zip'}[ext],
        headers={'Content-Disposition':f'attachment; filename="{doc["kind"]}-{fid}.{"zip" if ext=="cdr" else ext}"'})
