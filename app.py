#!/usr/bin/env python3
from alembic import command
from alembic.config import Config as AlembicConfig
from datatypes import ChannelOpenRequest
from datetime import datetime
from grpc._channel import _MultiThreadedRendezvous
from io import BytesIO
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.config import Config
from starlette.exceptions import HTTPException
from starlette.responses import UJSONResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from sqlalchemy.orm import sessionmaker

import base64
import click
import csv
import databases
import lnd_grpc
import lnurl
import qrcode
import sqlalchemy as sqla
import uvicorn

config = Config('.env')
DATABASE_URL = config('DATABASE_URL', cast=databases.DatabaseURL)

# Database table definitions.
metadata = sqla.MetaData()

invites = sqla.Table(
    'invites',
    metadata,
    sqla.Column('id', sqla.Integer, primary_key=True),
    sqla.Column('invite_code', sqla.String, index=True, unique=True),
    sqla.Column('node_id', sqla.String),
    sqla.Column('funding_amount', sqla.BigInteger, nullable=False),
    sqla.Column('push_amount', sqla.BigInteger, nullable=False, server_default=sqla.text('0')),  # noqa
    sqla.Column('is_used', sqla.Boolean, default=False, index=True),
    sqla.Column('used_at', sqla.DateTime),
    sqla.Column('created_at', sqla.DateTime, default=datetime.utcnow)
)

database = databases.Database(DATABASE_URL)
templates = Jinja2Templates(directory='templates')


# Application code
async def homepage(request):
    template = 'home.html'
    ctx = {'request': request}

    return templates.TemplateResponse(template, ctx)

async def index(request):
    buffer = BytesIO()
    template = 'index.html'
    ctx = {'request': request}
    k1 = request.path_params['k1']

    # check that the invite code exists
    query = invites.select().where(invites.c.invite_code == k1)
    res =  await database.fetch_one(query)

    if res:
        if res['is_used'] == False:
            lnurl_endpoint = lnurl.encode(config('BASE_URL') + \
                app.url_path_for('start', k1=k1))
            qr = qrcode.QRCode()
            qr.add_data('lightning:' + lnurl_endpoint)
            qr.make(fit=True)
            img = qr.make_image(fill_color='#343a40', back_color='white')

            img.save(buffer, format='PNG')

            ctx['lnurl'] = lnurl_endpoint
            ctx['lnurl_imagedata'] = base64.b64encode(buffer.getvalue()).decode()  # noqa

            return templates.TemplateResponse(template, ctx)
        else:
            raise HTTPException(status_code=410)
    else:
        raise HTTPException(status_code=404)

async def start(request):
    k1 = request.path_params['k1']

    query = invites.select().where(invites.c.invite_code == k1)
    res = await database.fetch_one(query)

    if res:
        # even though it could be skipped, we want to ensure the invite code
        # is valid before revealing any information
        if res['is_used'] == False:
            return UJSONResponse({
                'callback': request.url_for("connect"),
                'k1': k1,
                'uri': config('NODE_URI'),
                'tag': 'channelRequest'
            })
        else:
            return UJSONResponse({
                'status': 'ERROR',
                'reason': 'this invite code has been used'
            })
    else:
        return UJSONResponse({
            'status': 'ERROR',
            'reason': 'this invite code is invalid'
        })

async def connect(request):
    lnd_rpc = lnd_grpc.Client(
        network=config('LND_NETWORK', default='mainnet'),
        grpc_host=config('LND_GRPC_HOST', default='localhost'),
        grpc_port=config('LND_GRPC_PORT', default='10009'))

    try:
        req = ChannelOpenRequest(**request.query_params)

        try:
            query = invites.select().where(invites.c.invite_code == req.k1)
            res = await database.fetch_one(query)

            if res:
                if res['is_used'] == False:
                    next(lnd_rpc.open_channel(
                        node_pubkey=req.remoteid,
                        private=1 if config('LND_FORCE_PRIVATE', cast=bool, default=False) else req.private,  # noqa
                        local_funding_amount=res['funding_amount'],
                        push_sat=res['push_amount'],
                        spend_unconfirmed=config('LND_SPEND_UNCONFIRMED', cast=bool, default=True),  # noqa
                        sat_per_byte=config('LND_FEE_RATE', cast=int, default=None)))  # noqa

                    q = invites.update().where(invites.c.invite_code == req.k1) \
                        .values(
                            is_used=True,
                            node_id=req.remoteid.hex(),
                            used_at=datetime.utcnow())
                    await database.execute(q)

                    return UJSONResponse({'status': 'OK'})
                else:
                    return UJSONResponse({
                        'status': 'ERROR',
                        'reason': 'this invite code has been used'
                    })
            else:
                return UJSONResponse({
                    'status': 'ERROR',
                    'reason': 'this invite code is invalid'
                })
        except _MultiThreadedRendezvous as e:
            return UJSONResponse({
                'status': 'ERROR',
                'reason': e.details()
            })

    except ValidationError as e:
        return UJSONResponse({
            'status': 'ERROR',
            'reason': 'invalid parameter(s) provided'
        })


routes = [
    Mount('/static', app=StaticFiles(directory='static'), name='static'),
    Route('/', endpoint=homepage, name='home'),
    Route('/connect', endpoint=connect, name='connect'),
    Route('/s/{k1:str}', endpoint=start, name='start'),
    Route('/i/{k1:str}', endpoint=index, name='index')
]

app = Starlette(
    debug=True,
    routes=routes,
    on_startup=[database.connect],
    on_shutdown=[database.disconnect]
)


@click.group()
def cli():
    pass

@click.command()
def run():
    uvicorn.run(app, host='0.0.0.0', port=5000)

@click.command(help='loads a csv file containing invites into the local database')  # noqa
@click.argument('csvfile', type=click.File())
def load(csvfile):
    _invites = []

    csvreader = csv.reader(csvfile)
    for row in csvreader:
        _invites.append({
            'invite_code': row[0],
            'funding_amount': int(row[1]),
            'push_amount': int(row[2])
        })

    try:
        engine = sqla.create_engine(str(DATABASE_URL))
        conn = engine.connect()
        conn.execute(invites.insert(), _invites)

        print('{} invites loaded'.format(len(_invites)))
    except Exception as e:
        print(e)

@click.command()
def initdb():
    config = AlembicConfig('alembic.ini')
    command.upgrade(config, 'head')


cli.add_command(run)
cli.add_command(load)
cli.add_command(initdb)

if __name__ == '__main__':
    cli()
